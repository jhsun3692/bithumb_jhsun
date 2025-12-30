"""Web page routes for browser-based UI."""
from fastapi import APIRouter, Request, Depends, HTTPException, Form, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional
from app.core.database import get_db
from app.core.security import authenticate_user, create_access_token, decode_token
from app.models.user import User
from app.services.bithumb_api import bithumb_api
from datetime import timedelta, datetime

router = APIRouter(tags=["web"])
templates = Jinja2Templates(directory="app/templates")

# Add custom Jinja2 filters
import json

def fromjson_filter(value):
    """Convert JSON string to Python object."""
    try:
        return json.loads(value) if value else {}
    except:
        return {}

templates.env.filters["fromjson"] = fromjson_filter


def get_current_user_from_cookie(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    """Get current user from cookie token.

    Args:
        request: HTTP request
        db: Database session

    Returns:
        User object if authenticated, None otherwise
    """
    token = request.cookies.get("access_token")
    if not token:
        return None

    try:
        token_data = decode_token(token)
        user = db.query(User).filter(User.username == token_data.username).first()
        return user if user and user.is_active else None
    except:
        return None


def get_user_bithumb_api(user: User):
    """Get BithumbAPI instance for a specific user.

    Args:
        user: User object

    Returns:
        BithumbAPI instance with user's API keys
    """
    from app.services.bithumb_api import BithumbAPI
    return BithumbAPI(api_key=user.bithumb_api_key, api_secret=user.bithumb_api_secret)


@router.get("/", response_class=HTMLResponse)
async def home(request: Request, db: Session = Depends(get_db)):
    """Home page."""
    user = get_current_user_from_cookie(request, db)

    if user:
        return RedirectResponse(url="/dashboard", status_code=302)

    return templates.TemplateResponse("index.html", {"request": request})


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, db: Session = Depends(get_db)):
    """Login page."""
    user = get_current_user_from_cookie(request, db)
    if user:
        return RedirectResponse(url="/dashboard", status_code=302)

    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login")
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    otp_code: str = Form(""),
    db: Session = Depends(get_db)
):
    """Handle login form submission."""
    user = authenticate_user(db, username, password)

    if not user:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "사용자명 또는 비밀번호가 올바르지 않습니다"}
        )

    # Check if user has 2FA enabled
    if user.otp_enabled:
        # If OTP code is not provided, create temporary token and show OTP input
        if not otp_code:
            # Create temporary token (5 minutes expiry) for 2FA verification
            temp_token = create_access_token(
                data={"sub": user.username, "temp_2fa": True},
                expires_delta=timedelta(minutes=5)
            )

            response = templates.TemplateResponse(
                "login.html",
                {
                    "request": request,
                    "require_otp": True,
                    "username": username
                }
            )
            response.set_cookie(
                key="temp_2fa_token",
                value=temp_token,
                httponly=True,
                max_age=300,  # 5 minutes
                samesite="lax"
            )
            return response

        # Verify OTP code
        import pyotp
        totp = pyotp.TOTP(user.otp_secret)

        if not totp.verify(otp_code, valid_window=1):
            return templates.TemplateResponse(
                "login.html",
                {
                    "request": request,
                    "require_otp": True,
                    "username": username,
                    "error": "OTP 코드가 올바르지 않습니다"
                }
            )

    # Create access token
    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=timedelta(hours=24)
    )

    response = RedirectResponse(url="/dashboard", status_code=302)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=86400,  # 24 hours
        samesite="lax"
    )
    # Clear temporary 2FA token if exists
    response.delete_cookie("temp_2fa_token")

    return response


@router.post("/login/verify-otp")
async def verify_otp_login(
    request: Request,
    otp_code: str = Form(...),
    db: Session = Depends(get_db)
):
    """Verify OTP code for 2FA login."""
    # Get temporary 2FA token from cookie
    temp_token = request.cookies.get("temp_2fa_token")

    if not temp_token:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "세션이 만료되었습니다. 다시 로그인해주세요."}
        )

    try:
        # Decode JWT token directly to access all payload fields
        from jose import jwt, JWTError
        from app.core.config import get_settings

        settings = get_settings()
        payload = jwt.decode(temp_token, settings.jwt_secret_key, algorithms=["HS256"])

        username = payload.get("sub")
        is_temp_2fa = payload.get("temp_2fa", False)

        # Check if it's a valid temporary 2FA token
        if not username or not is_temp_2fa:
            return templates.TemplateResponse(
                "login.html",
                {"request": request, "error": "잘못된 인증 세션입니다."}
            )

        # Get user from database
        user = db.query(User).filter(User.username == username).first()

        if not user or not user.otp_enabled or not user.otp_secret:
            return templates.TemplateResponse(
                "login.html",
                {"request": request, "error": "사용자를 찾을 수 없습니다."}
            )

        # Verify OTP code
        import pyotp
        totp = pyotp.TOTP(user.otp_secret)

        if not totp.verify(otp_code, valid_window=1):
            return templates.TemplateResponse(
                "login.html",
                {
                    "request": request,
                    "require_otp": True,
                    "username": user.username,
                    "error": "OTP 코드가 올바르지 않습니다"
                }
            )

        # OTP verified successfully, create access token
        access_token = create_access_token(
            data={"sub": user.username},
            expires_delta=timedelta(hours=24)
        )

        response = RedirectResponse(url="/dashboard", status_code=302)
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            max_age=86400,  # 24 hours
            samesite="lax"
        )
        # Clear temporary 2FA token
        response.delete_cookie("temp_2fa_token")

        return response

    except JWTError as e:
        print(f"JWT decode error: {e}")
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "세션이 만료되었거나 잘못되었습니다. 다시 로그인해주세요."}
        )
    except Exception as e:
        print(f"OTP verification error: {e}")
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "인증 중 오류가 발생했습니다. 다시 로그인해주세요."}
        )


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, db: Session = Depends(get_db)):
    """Registration page."""
    user = get_current_user_from_cookie(request, db)
    if user:
        return RedirectResponse(url="/dashboard", status_code=302)

    return templates.TemplateResponse("register.html", {"request": request})


@router.post("/register")
async def register_submit(
    request: Request,
    email: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Handle registration form submission."""
    # Validate passwords match
    if password != confirm_password:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Passwords do not match"}
        )

    # Check if username exists
    if db.query(User).filter(User.username == username).first():
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Username already exists"}
        )

    # Check if email exists
    if db.query(User).filter(User.email == email).first():
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Email already registered"}
        )

    # Create user
    from app.core.security import get_password_hash
    new_user = User(
        email=email,
        username=username,
        hashed_password=get_password_hash(password)
    )
    db.add(new_user)
    db.commit()

    return RedirectResponse(url="/login?registered=true", status_code=302)


@router.get("/logout")
async def logout():
    """Logout user."""
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("access_token")
    return response


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    """Dashboard page showing strategy performance."""
    user = get_current_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    # Check if user is approved
    if not user.is_approved and not user.is_admin:
        return RedirectResponse(url="/pending-approval", status_code=302)

    from app.models.database import TradingStrategy, StrategyExecutionLog
    from sqlalchemy import func

    # Get user's Bithumb API instance
    user_api = get_user_bithumb_api(user)

    # Get all strategies with their performance
    strategies = db.query(TradingStrategy).all()

    # 활성화된 전략의 코인 목록 수집
    active_strategy_coins = set()
    for strategy in strategies:
        if strategy.enabled:
            active_strategy_coins.add(strategy.coin)

    # KRW 잔고 조회 (사용자별 API 사용)
    krw_balance_data = user_api.get_krw_balance()
    krw_available = krw_balance_data.get("available", 0.0)
    krw_total = krw_balance_data.get("total", 0.0)

    # API 에러 메시지 수집
    api_error = None

    # 보유 코인 캐시 (중복 API 호출 방지)
    balance_cache = {}

    # 보유 코인 목록과 현재 가치 계산
    balances = []
    current_value = 0.0
    total_invested = 0.0

    # 활성화된 전략의 코인만 조회
    for coin in active_strategy_coins:
        try:
            coin_balance_data = user_api.get_balance(coin)
            balance_cache[coin] = coin_balance_data

            # API 에러 체크
            if not api_error and "error" in coin_balance_data:
                error_val = coin_balance_data["error"]
                if isinstance(error_val, dict):
                    api_error = error_val.get("message", str(error_val))
                else:
                    api_error = str(error_val)

            coin_total = coin_balance_data.get("total", 0.0)

            if coin_total > 0:
                # 현재 가격 조회
                current_price = user_api.get_current_price(coin)
                if current_price:
                    coin_value = coin_total * current_price
                    current_value += coin_value

                    # 평균 매수가
                    avg_buy_price = coin_balance_data.get("avg_buy_price")

                    # 투자금 계산
                    if avg_buy_price:
                        coin_invested = avg_buy_price * coin_total
                        total_invested += coin_invested

                    # 잔고 정보 추가
                    balances.append({
                        "coin": coin,
                        "total": coin_total,
                        "avg_buy_price": avg_buy_price,
                        "current_price": current_price,
                        "current_value": coin_value
                    })
        except Exception as e:
            print(f"Error processing balance for {coin}: {e}")

    # 총 수익 및 ROI 계산
    total_profit = current_value - total_invested
    roi = (total_profit / total_invested * 100) if total_invested > 0 else 0

    # 활성 전략 정보 (캐시 사용하여 중복 API 호출 방지)
    active_strategies = []
    for strategy in strategies:
        try:
            params = json.loads(strategy.parameters) if strategy.parameters else {}
        except:
            params = {}

        # 캐시에서 잔고 정보 가져오기, 없으면 API 호출
        if strategy.coin in balance_cache:
            balance_data = balance_cache[strategy.coin]
        else:
            balance_data = user_api.get_balance(strategy.coin)
            balance_cache[strategy.coin] = balance_data

        coin_total = balance_data.get("total", 0.0)
        avg_buy_price = balance_data.get("avg_buy_price")

        strat_invested = 0.0
        strat_value = 0.0
        strat_profit = 0.0

        if coin_total > 0 and avg_buy_price:
            strat_invested = avg_buy_price * coin_total
            current_price = user_api.get_current_price(strategy.coin)
            if current_price:
                strat_value = coin_total * current_price
                strat_profit = (current_price - avg_buy_price) * coin_total

        strat_roi = (strat_profit / strat_invested * 100) if strat_invested > 0 else 0

        active_strategies.append({
            "name": strategy.name,
            "coin": strategy.coin,
            "strategy_type": strategy.strategy_type,
            "enabled": strategy.enabled,
            "total_invested": strat_invested,
            "current_value": strat_value,
            "total_profit": strat_profit,
            "roi": strat_roi
        })

    # 최근 전략 실행 로그
    execution_logs = db.query(StrategyExecutionLog).order_by(
        StrategyExecutionLog.created_at.desc()
    ).limit(20).all()

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "total_invested": total_invested,
            "current_value": current_value,
            "total_profit": total_profit,
            "roi": roi,
            "krw_balance": krw_total,
            "krw_available": krw_available,
            "balances": balances,
            "active_strategies": active_strategies,
            "execution_logs": execution_logs,
            "api_error": api_error
        }
    )


@router.get("/strategy", response_class=HTMLResponse)
async def strategy_page(request: Request, db: Session = Depends(get_db)):
    """Strategy management page."""
    user = get_current_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    # Check if user is approved
    if not user.is_approved and not user.is_admin:
        return RedirectResponse(url="/pending-approval", status_code=302)

    # Get user's Bithumb API instance
    user_api = get_user_bithumb_api(user)

    # Get all strategies
    from app.models.database import TradingStrategy, Order, OrderType, OrderStatus
    strategies = db.query(TradingStrategy).all()

    # Get available coins from Bithumb (public API, no auth needed)
    available_coins = bithumb_api.get_available_coins()

    # Calculate performance for each strategy
    strategy_performances = []
    for strategy in strategies:
        try:
            params = json.loads(strategy.parameters) if strategy.parameters else {}
        except:
            params = {}

        # Get current holdings from API (사용자별 API 사용)
        balance_data = user_api.get_balance(strategy.coin)
        coin_total = balance_data.get("total", 0.0)
        avg_buy_price = balance_data.get("avg_buy_price")

        # Calculate investment and profit based on API balance
        total_invested = 0.0
        current_value = 0.0
        total_profit = 0.0

        if coin_total > 0 and avg_buy_price:
            # 투자금 = 평균 매수가 × 보유량
            total_invested = avg_buy_price * coin_total

            # 현재 가격 조회 (사용자별 API 사용)
            current_price = user_api.get_current_price(strategy.coin)
            if current_price:
                # 현재 가치 = 현재가 × 보유량
                current_value = coin_total * current_price

                # 미실현 수익 = (현재가 - 평균 매수가) × 보유량
                total_profit = (current_price - avg_buy_price) * coin_total

        # ROI calculation
        roi = (total_profit / total_invested * 100) if total_invested > 0 else 0

        strategy_performances.append({
            "strategy": strategy,
            "params": params,
            "total_invested": total_invested,
            "current_value": current_value,
            "total_profit": total_profit,
            "roi": roi,
            "holdings": coin_total
        })

    return templates.TemplateResponse(
        "strategy.html",
        {
            "request": request,
            "user": user,
            "strategy_performances": strategy_performances,
            "available_coins": available_coins
        }
    )


@router.post("/strategy/bollinger")
async def create_bollinger_strategy(
    request: Request,
    coin: str = Form(...),
    trade_amount_krw: float = Form(...),
    profit_target: float = Form(5.0),
    stop_loss: float = Form(0.0),
    period: int = Form(20),
    std_dev: float = Form(2.0),
    db: Session = Depends(get_db)
):
    """Create a Bollinger Band strategy."""
    user = get_current_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    from app.models.database import TradingStrategy
    import json
    from datetime import datetime

    # Get current price to calculate trade_amount (in coin units)
    from app.services.bithumb_api import bithumb_api
    current_price = bithumb_api.get_current_price(coin)
    trade_amount = trade_amount_krw / current_price if current_price else 0.001

    # Generate unique strategy name
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    strategy_name = f"Bollinger-{coin}-{period}-{timestamp}"

    # Check if strategy with similar name exists
    existing = db.query(TradingStrategy).filter(
        TradingStrategy.coin == coin,
        TradingStrategy.strategy_type == "bollinger",
        TradingStrategy.enabled == True
    ).first()

    if existing:
        return RedirectResponse(
            url="/strategy?error=duplicate",
            status_code=302
        )

    # Create strategy with all parameters
    strategy = TradingStrategy(
        user_id=user.id,
        name=strategy_name,
        coin=coin,
        enabled=True,
        strategy_type="bollinger",
        parameters=json.dumps({
            "period": period,
            "std_dev": std_dev,
            "trade_amount": trade_amount,
            "trade_amount_krw": trade_amount_krw,
            "profit_target": profit_target,
            "stop_loss": stop_loss
        })
    )
    db.add(strategy)
    db.commit()

    return RedirectResponse(url="/strategy?success=true", status_code=302)


@router.post("/strategy/ma")
async def create_ma_strategy(
    request: Request,
    coin: str = Form(...),
    trade_amount_krw: float = Form(...),
    profit_target: float = Form(5.0),
    stop_loss: float = Form(0.0),
    short_period: int = Form(5),
    long_period: int = Form(20),
    db: Session = Depends(get_db)
):
    """Create a Moving Average strategy."""
    user = get_current_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    from app.models.database import TradingStrategy
    import json
    from datetime import datetime

    # Get current price to calculate trade_amount (in coin units)
    current_price = bithumb_api.get_current_price(coin)
    trade_amount = trade_amount_krw / current_price if current_price else 0.001

    # Generate unique strategy name
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    strategy_name = f"MA-{coin}-{short_period}-{long_period}-{timestamp}"

    # Check if strategy with similar configuration exists
    existing = db.query(TradingStrategy).filter(
        TradingStrategy.coin == coin,
        TradingStrategy.strategy_type == "moving_average",
        TradingStrategy.enabled == True
    ).first()

    if existing:
        return RedirectResponse(
            url="/strategy?error=duplicate",
            status_code=302
        )

    strategy = TradingStrategy(
        user_id=user.id,
        name=strategy_name,
        coin=coin,
        enabled=True,
        strategy_type="moving_average",
        parameters=json.dumps({
            "short_period": short_period,
            "long_period": long_period,
            "trade_amount": trade_amount,
            "trade_amount_krw": trade_amount_krw,
            "profit_target": profit_target,
            "stop_loss": stop_loss
        })
    )
    db.add(strategy)
    db.commit()

    return RedirectResponse(url="/strategy?success=true", status_code=302)


@router.post("/strategy/rsi")
async def create_rsi_strategy(
    request: Request,
    coin: str = Form(...),
    trade_amount_krw: float = Form(...),
    profit_target: float = Form(5.0),
    stop_loss: float = Form(0.0),
    period: int = Form(14),
    oversold: int = Form(30),
    overbought: int = Form(70),
    db: Session = Depends(get_db)
):
    """Create an RSI strategy."""
    user = get_current_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    from app.models.database import TradingStrategy
    import json
    from datetime import datetime

    # Get current price to calculate trade_amount (in coin units)
    current_price = bithumb_api.get_current_price(coin)
    trade_amount = trade_amount_krw / current_price if current_price else 0.001

    # Generate unique strategy name
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    strategy_name = f"RSI-{coin}-{period}-{timestamp}"

    # Check if strategy with similar configuration exists
    existing = db.query(TradingStrategy).filter(
        TradingStrategy.coin == coin,
        TradingStrategy.strategy_type == "rsi",
        TradingStrategy.enabled == True
    ).first()

    if existing:
        return RedirectResponse(
            url="/strategy?error=duplicate",
            status_code=302
        )

    strategy = TradingStrategy(
        user_id=user.id,
        name=strategy_name,
        coin=coin,
        enabled=True,
        strategy_type="rsi",
        parameters=json.dumps({
            "period": period,
            "oversold": oversold,
            "overbought": overbought,
            "trade_amount": trade_amount,
            "trade_amount_krw": trade_amount_krw,
            "profit_target": profit_target,
            "stop_loss": stop_loss
        })
    )
    db.add(strategy)
    db.commit()

    return RedirectResponse(url="/strategy?success=true", status_code=302)


@router.post("/strategy/create")
async def create_strategy_unified(
    request: Request,
    db: Session = Depends(get_db)
):
    """Unified endpoint for creating any strategy type."""
    user = get_current_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    from app.models.database import TradingStrategy
    from datetime import datetime

    # Parse form data
    form_data = await request.form()
    strategy_type = form_data.get("strategy_type")
    coin = form_data.get("coin")
    trade_amount_krw = float(form_data.get("trade_amount_krw", 10000))
    max_buy_amount = float(form_data.get("max_buy_amount", 0))
    profit_target = float(form_data.get("profit_target", 5.0))
    stop_loss = float(form_data.get("stop_loss", 0.0))

    # Get current price to calculate trade_amount (in coin units)
    current_price = bithumb_api.get_current_price(coin)
    trade_amount = trade_amount_krw / current_price if current_price else 0.001

    # Build strategy parameters based on type
    params = {
        "trade_amount": trade_amount,
        "trade_amount_krw": trade_amount_krw,
        "profit_target": profit_target,
        "stop_loss": stop_loss
    }

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if strategy_type == "bollinger":
        params["period"] = int(form_data.get("period", 20))
        params["std_dev"] = float(form_data.get("std_dev", 2.0))
        strategy_name = f"Bollinger-{coin}-{params['period']}-{timestamp}"

    elif strategy_type == "moving_average":
        params["short_period"] = int(form_data.get("short_period", 5))
        params["long_period"] = int(form_data.get("long_period", 20))
        strategy_name = f"MA-{coin}-{params['short_period']}-{params['long_period']}-{timestamp}"

    elif strategy_type == "rsi":
        params["period"] = int(form_data.get("period", 14))
        params["oversold"] = int(form_data.get("oversold", 30))
        params["overbought"] = int(form_data.get("overbought", 70))
        strategy_name = f"RSI-{coin}-{params['period']}-{timestamp}"

    elif strategy_type == "macd":
        params["fast_period"] = int(form_data.get("fast_period", 12))
        params["slow_period"] = int(form_data.get("slow_period", 26))
        params["signal_period"] = int(form_data.get("signal_period", 9))
        strategy_name = f"MACD-{coin}-{params['fast_period']}-{params['slow_period']}-{timestamp}"

    elif strategy_type == "stochastic":
        params["k_period"] = int(form_data.get("k_period", 14))
        params["d_period"] = int(form_data.get("d_period", 3))
        params["oversold"] = int(form_data.get("oversold", 20))
        params["overbought"] = int(form_data.get("overbought", 80))
        strategy_name = f"Stochastic-{coin}-{params['k_period']}-{timestamp}"

    elif strategy_type == "composite":
        # Get list of selected strategy types
        strategy_types = form_data.getlist("strategy_types")
        params["strategy_types"] = strategy_types
        params["min_confirmations"] = int(form_data.get("min_confirmations", 2))
        strategy_name = f"Composite-{coin}-{len(strategy_types)}-{timestamp}"
    else:
        return RedirectResponse(url="/strategy?error=invalid_type", status_code=302)

    # Check for duplicate active strategy
    existing = db.query(TradingStrategy).filter(
        TradingStrategy.coin == coin,
        TradingStrategy.strategy_type == strategy_type,
        TradingStrategy.enabled == True
    ).first()

    if existing:
        return RedirectResponse(url="/strategy?error=duplicate", status_code=302)

    # Create strategy
    strategy = TradingStrategy(
        user_id=user.id,
        name=strategy_name,
        coin=coin,
        enabled=True,
        strategy_type=strategy_type,
        parameters=json.dumps(params),
        max_buy_amount=max_buy_amount if max_buy_amount > 0 else None
    )
    db.add(strategy)
    db.commit()

    return RedirectResponse(url="/strategy?success=true", status_code=302)


@router.post("/strategy/toggle/{strategy_id}")
async def toggle_strategy(
    request: Request,
    strategy_id: int,
    db: Session = Depends(get_db)
):
    """Toggle strategy enabled/disabled."""
    user = get_current_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    from app.models.database import TradingStrategy
    strategy = db.query(TradingStrategy).filter(TradingStrategy.id == strategy_id).first()

    if strategy:
        strategy.enabled = not strategy.enabled
        db.commit()

    return RedirectResponse(url="/strategy", status_code=302)


@router.post("/strategy/delete/{strategy_id}")
async def delete_strategy(
    request: Request,
    strategy_id: int,
    db: Session = Depends(get_db)
):
    """Delete a strategy."""
    user = get_current_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    from app.models.database import TradingStrategy
    strategy = db.query(TradingStrategy).filter(TradingStrategy.id == strategy_id).first()

    if strategy:
        db.delete(strategy)
        db.commit()

    return RedirectResponse(url="/strategy", status_code=302)


@router.get("/strategy/logs/{strategy_id}", response_class=HTMLResponse)
async def strategy_logs(
    request: Request,
    strategy_id: int,
    page: int = 1,
    db: Session = Depends(get_db)
):
    """View detailed execution logs for a specific strategy."""
    user = get_current_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    from app.models.database import TradingStrategy, StrategyExecutionLog

    # Get strategy
    strategy = db.query(TradingStrategy).filter(TradingStrategy.id == strategy_id).first()
    if not strategy:
        return RedirectResponse(url="/strategy", status_code=302)

    # Parse parameters
    try:
        params = json.loads(strategy.parameters) if strategy.parameters else {}
    except:
        params = {}

    # Pagination
    per_page = 50
    offset = (page - 1) * per_page

    # Get logs for this strategy
    logs = db.query(StrategyExecutionLog).filter(
        StrategyExecutionLog.strategy_name == strategy.name
    ).order_by(
        StrategyExecutionLog.created_at.desc()
    ).limit(per_page).offset(offset).all()

    # Get execution statistics
    total_executions = db.query(StrategyExecutionLog).filter(
        StrategyExecutionLog.strategy_name == strategy.name
    ).count()

    buy_signals = db.query(StrategyExecutionLog).filter(
        StrategyExecutionLog.strategy_name == strategy.name,
        StrategyExecutionLog.signal == 'buy'
    ).count()

    sell_signals = db.query(StrategyExecutionLog).filter(
        StrategyExecutionLog.strategy_name == strategy.name,
        StrategyExecutionLog.signal == 'sell'
    ).count()

    hold_signals = db.query(StrategyExecutionLog).filter(
        StrategyExecutionLog.strategy_name == strategy.name,
        StrategyExecutionLog.signal == 'hold'
    ).count()

    return templates.TemplateResponse(
        "strategy_logs.html",
        {
            "request": request,
            "user": user,
            "strategy": strategy,
            "params": params,
            "logs": logs,
            "total_executions": total_executions,
            "buy_signals": buy_signals,
            "sell_signals": sell_signals,
            "hold_signals": hold_signals,
            "page": page,
            "per_page": per_page
        }
    )


@router.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request, db: Session = Depends(get_db)):
    """User profile page."""
    user = get_current_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    return templates.TemplateResponse(
        "profile.html",
        {
            "request": request,
            "user": user,
            "qr_code_uri": None,
            "otp_secret": None
        }
    )


@router.post("/profile/update")
async def update_profile(
    request: Request,
    email: str = Form(...),
    db: Session = Depends(get_db)
):
    """Update user profile information."""
    user = get_current_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    # Check if email is already taken by another user
    existing_user = db.query(User).filter(
        User.email == email,
        User.id != user.id
    ).first()

    if existing_user:
        return templates.TemplateResponse(
            "profile.html",
            {
                "request": request,
                "user": user,
                "error": "이메일이 이미 사용 중입니다"
            }
        )

    # Update user email
    user.email = email
    db.commit()

    return RedirectResponse(url="/profile?success=profile", status_code=302)


@router.post("/profile/change-password")
async def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Change user password."""
    user = get_current_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    from app.core.security import verify_password, get_password_hash

    # Verify current password
    if not verify_password(current_password, user.hashed_password):
        return templates.TemplateResponse(
            "profile.html",
            {
                "request": request,
                "user": user,
                "error": "현재 비밀번호가 올바르지 않습니다"
            }
        )

    # Validate new passwords match
    if new_password != confirm_password:
        return templates.TemplateResponse(
            "profile.html",
            {
                "request": request,
                "user": user,
                "error": "새 비밀번호가 일치하지 않습니다"
            }
        )

    # Update password
    user.hashed_password = get_password_hash(new_password)
    db.commit()

    return RedirectResponse(url="/profile?success=password", status_code=302)


@router.post("/profile/update-api")
async def update_api_keys(
    request: Request,
    api_key: str = Form(""),
    api_secret: str = Form(""),
    db: Session = Depends(get_db)
):
    """Update Bithumb API keys."""
    user = get_current_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    # Update API keys (only if provided)
    if api_key:
        user.bithumb_api_key = api_key
    if api_secret:
        user.bithumb_api_secret = api_secret

    db.commit()

    return RedirectResponse(url="/profile?success=api", status_code=302)


# 2FA Routes
@router.post("/profile/setup-2fa")
async def setup_2fa(request: Request, db: Session = Depends(get_db)):
    """Setup 2FA by generating OTP secret and QR code."""
    user = get_current_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    # Check if 2FA is already enabled
    if user.otp_enabled:
        return RedirectResponse(url="/profile", status_code=302)

    import pyotp
    import qrcode
    from io import BytesIO
    import base64

    # Generate new OTP secret
    otp_secret = pyotp.random_base32()

    # Save temporary secret to session (not yet activated)
    user.otp_secret = otp_secret
    db.commit()

    # Generate provisioning URI for QR code
    # Format: otpauth://totp/ServiceName:username?secret=SECRET&issuer=ServiceName
    totp_uri = pyotp.totp.TOTP(otp_secret).provisioning_uri(
        name=user.username,
        issuer_name="Bithumb AutoTrading"
    )

    # Generate QR code
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(totp_uri)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    # Convert QR code to base64 data URI
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    img_base64 = base64.b64encode(buffer.getvalue()).decode()
    qr_code_uri = f"data:image/png;base64,{img_base64}"

    return templates.TemplateResponse(
        "profile.html",
        {
            "request": request,
            "user": user,
            "qr_code_uri": qr_code_uri,
            "otp_secret": otp_secret
        }
    )


@router.post("/profile/verify-2fa")
async def verify_2fa(
    request: Request,
    otp_code: str = Form(...),
    db: Session = Depends(get_db)
):
    """Verify OTP code and activate 2FA."""
    user = get_current_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    # Check if user has OTP secret
    if not user.otp_secret:
        return templates.TemplateResponse(
            "profile.html",
            {
                "request": request,
                "user": user,
                "error": "2FA 설정이 시작되지 않았습니다. 다시 시도해주세요.",
                "qr_code_uri": None,
                "otp_secret": None
            }
        )

    import pyotp

    # Verify OTP code
    totp = pyotp.TOTP(user.otp_secret)

    if totp.verify(otp_code, valid_window=1):
        # Code is valid, activate 2FA
        user.otp_enabled = True
        db.commit()

        return RedirectResponse(url="/profile?success=2fa_enabled", status_code=302)
    else:
        # Code is invalid
        # Re-generate QR code for display
        import qrcode
        from io import BytesIO
        import base64

        totp_uri = pyotp.totp.TOTP(user.otp_secret).provisioning_uri(
            name=user.username,
            issuer_name="Bithumb AutoTrading"
        )

        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(totp_uri)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        img_base64 = base64.b64encode(buffer.getvalue()).decode()
        qr_code_uri = f"data:image/png;base64,{img_base64}"

        return templates.TemplateResponse(
            "profile.html",
            {
                "request": request,
                "user": user,
                "error": "인증 코드가 올바르지 않습니다. 다시 시도해주세요.",
                "qr_code_uri": qr_code_uri,
                "otp_secret": user.otp_secret
            }
        )


@router.post("/profile/disable-2fa")
async def disable_2fa(request: Request, db: Session = Depends(get_db)):
    """Disable 2FA for user."""
    user = get_current_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    # Disable 2FA
    user.otp_enabled = False
    user.otp_secret = None
    db.commit()

    return RedirectResponse(url="/profile?success=2fa_disabled", status_code=302)


@router.get("/pending-approval", response_class=HTMLResponse)
async def pending_approval_page(request: Request, db: Session = Depends(get_db)):
    """Pending approval page for unapproved users."""
    user = get_current_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    # If user is approved or admin, redirect to dashboard
    if user.is_approved or user.is_admin:
        return RedirectResponse(url="/dashboard", status_code=302)

    return templates.TemplateResponse(
        "pending_approval.html",
        {
            "request": request,
            "user": user
        }
    )


# Admin Routes
@router.get("/admin/users", response_class=HTMLResponse)
async def admin_users_page(request: Request, db: Session = Depends(get_db)):
    """Admin page for user management."""
    user = get_current_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    # Check if user is admin
    if not user.is_admin:
        return RedirectResponse(url="/dashboard", status_code=302)

    # Get pending users
    pending_users = db.query(User).filter(
        User.is_approved == False,
        User.is_admin == False
    ).all()

    # Get approved users
    approved_users = db.query(User).filter(
        User.is_approved == True
    ).all()

    return templates.TemplateResponse(
        "admin_users.html",
        {
            "request": request,
            "user": user,
            "pending_users": pending_users,
            "approved_users": approved_users
        }
    )


@router.post("/admin/users/approve/{user_id}")
async def approve_user(
    request: Request,
    user_id: int,
    db: Session = Depends(get_db)
):
    """Approve a user."""
    admin = get_current_user_from_cookie(request, db)
    if not admin or not admin.is_admin:
        return RedirectResponse(url="/login", status_code=302)

    user_to_approve = db.query(User).filter(User.id == user_id).first()
    if user_to_approve:
        user_to_approve.is_approved = True
        db.commit()

    return RedirectResponse(url="/admin/users?success=approved", status_code=302)


@router.post("/admin/users/reject/{user_id}")
async def reject_user(
    request: Request,
    user_id: int,
    db: Session = Depends(get_db)
):
    """Reject (delete) a user."""
    admin = get_current_user_from_cookie(request, db)
    if not admin or not admin.is_admin:
        return RedirectResponse(url="/login", status_code=302)

    user_to_reject = db.query(User).filter(User.id == user_id).first()
    if user_to_reject and not user_to_reject.is_admin:
        db.delete(user_to_reject)
        db.commit()

    return RedirectResponse(url="/admin/users?success=rejected", status_code=302)


@router.post("/admin/users/toggle-active/{user_id}")
async def toggle_user_active(
    request: Request,
    user_id: int,
    db: Session = Depends(get_db)
):
    """Toggle user active/inactive status."""
    admin = get_current_user_from_cookie(request, db)
    if not admin or not admin.is_admin:
        return RedirectResponse(url="/login", status_code=302)

    user_to_toggle = db.query(User).filter(User.id == user_id).first()
    if user_to_toggle and not user_to_toggle.is_admin:
        user_to_toggle.is_active = not user_to_toggle.is_active
        db.commit()

    return RedirectResponse(url="/admin/users", status_code=302)
