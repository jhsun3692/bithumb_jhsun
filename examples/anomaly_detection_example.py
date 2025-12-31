"""이상 탐지 예제 스크립트

이 스크립트는 실시간으로 가격, 거래량, 전략 성과 이상을 감지하는 방법을 보여줍니다.
"""
import sys
import os

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.anomaly_detector import AnomalyDetector
from app.services.bithumb_api import BithumbAPI
import time
from datetime import datetime


def print_separator():
    """구분선 출력"""
    print("="*80)


def check_price_anomalies(detector, coin):
    """가격 이상 탐지"""
    print(f"\n🔍 [{coin}] 가격 이상 탐지 중...")

    result = detector.detect_price_anomalies(coin, threshold=3.0, lookback_days=30)

    if result.get("error"):
        print(f"❌ 오류: {result['error']}")
        return

    print(f"  현재가: {result['current_price']:,.0f}원")
    print(f"  변화율: {result['current_change_pct']:+.2f}%")
    print(f"  Z-score: {result['current_z_score']:+.2f}")
    print(f"  평균 변화율: {result['mean_change']:.2f}%")
    print(f"  표준편차: {result['std_change']:.2f}%")

    if result["is_anomaly"]:
        print(f"\n⚠️  가격 이상 감지!")
        print(f"  타입: {result['anomaly_type']}")
        print(f"  심각도: {result['severity']}")
        print(f"  권장사항: {result['recommendation']}")
    else:
        print(f"\n✅ 정상 범위 내 가격 변동")


def check_volume_anomalies(detector, coin):
    """거래량 이상 탐지"""
    print(f"\n🔍 [{coin}] 거래량 이상 탐지 중...")

    result = detector.detect_volume_anomalies(coin, threshold=2.5, lookback_days=30)

    if result.get("error"):
        print(f"❌ 오류: {result['error']}")
        return

    print(f"  현재 거래량: {result['current_volume']:,.0f}")
    print(f"  평균 거래량: {result['mean_volume']:,.0f}")
    print(f"  평균 대비 비율: {result['volume_ratio']:.2f}x")
    print(f"  Z-score: {result['volume_z_score']:+.2f}")

    if result["is_anomaly"]:
        print(f"\n⚠️  거래량 이상 감지!")
        print(f"  타입: {result['anomaly_type']}")
        print(f"  심각도: {result['severity']}")

        if result['anomaly_type'] == 'high_volume':
            print(f"  → 거래량이 평균보다 {result['volume_ratio']:.1f}배 높습니다.")
            print(f"  → 시장 관심 증가 또는 대량 거래 발생 가능성")
        else:
            print(f"  → 거래량이 평균보다 낮습니다.")
            print(f"  → 시장 관심 감소 또는 유동성 부족 가능성")
    else:
        print(f"\n✅ 정상 범위 내 거래량")


def comprehensive_check(detector, coin):
    """종합 이상 탐지"""
    print(f"\n🔍 [{coin}] 종합 이상 탐지 실행 중...")

    result = detector.comprehensive_anomaly_check(coin)

    print(f"\n📊 종합 분석 결과:")
    print(f"  검사 시각: {result['timestamp']}")
    print(f"  전체 리스크 레벨: {result['overall_risk_level'].upper()}")

    # 리스크 레벨에 따른 이모지
    risk_emoji = {
        "minimal": "🟢",
        "low": "🟡",
        "medium": "🟠",
        "high": "🔴",
        "critical": "🚨"
    }
    emoji = risk_emoji.get(result['overall_risk_level'], "❓")

    print(f"  상태: {emoji} {result['overall_risk_level'].upper()}")

    if result['should_pause_trading']:
        print(f"\n🚨 경고: 거래 일시 중지 권장!")
        print(f"  → 리스크가 높아 자동 매매를 중단하는 것이 안전합니다.")

    return result


def monitor_continuously(api_key, api_secret, coins, interval_seconds=300):
    """지속적인 모니터링

    Args:
        api_key: Bithumb API 키
        api_secret: Bithumb API 시크릿
        coins: 모니터링할 코인 리스트
        interval_seconds: 체크 간격 (초)
    """
    api = BithumbAPI(api_key=api_key, api_secret=api_secret)
    detector = AnomalyDetector(api)

    print("\n🤖 지속적 모니터링 모드 시작")
    print(f"대상 코인: {', '.join(coins)}")
    print(f"체크 간격: {interval_seconds}초")
    print(f"중지하려면 Ctrl+C를 누르세요\n")

    try:
        while True:
            print_separator()
            print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print_separator()

            for coin in coins:
                try:
                    # 종합 이상 탐지
                    result = comprehensive_check(detector, coin)

                    # 리스크가 높으면 상세 정보 출력
                    if result['overall_risk_level'] in ['high', 'critical']:
                        print(f"\n⚠️  [{coin}] 상세 분석:")
                        check_price_anomalies(detector, coin)
                        check_volume_anomalies(detector, coin)

                except Exception as e:
                    print(f"❌ [{coin}] 오류: {e}")

            print(f"\n💤 {interval_seconds}초 대기 중...")
            time.sleep(interval_seconds)

    except KeyboardInterrupt:
        print("\n\n👋 모니터링을 종료합니다.")


def main():
    """메인 함수"""
    # API 키 설정 (실제 키로 변경하세요)
    API_KEY = ""  # Bithumb API 키
    API_SECRET = ""  # Bithumb API 시크릿

    if not API_KEY or not API_SECRET:
        print("⚠️ API 키와 시크릿을 설정해주세요!")
        print("이 스크립트 상단의 API_KEY와 API_SECRET 변수를 수정하세요.")
        return

    # 모니터링 설정
    COINS = ["BTC", "ETH", "XRP"]  # 모니터링할 코인 목록
    MODE = "once"  # "once" 또는 "continuous"
    CHECK_INTERVAL = 300  # 지속 모드일 때 체크 간격 (초)

    print_separator()
    print("빗썸 자동매매 이상 탐지 시스템")
    print_separator()

    api = BithumbAPI(api_key=API_KEY, api_secret=API_SECRET)
    detector = AnomalyDetector(api)

    if MODE == "continuous":
        # 지속적 모니터링
        monitor_continuously(API_KEY, API_SECRET, COINS, CHECK_INTERVAL)
    else:
        # 1회 체크
        for coin in COINS:
            try:
                print(f"\n{'='*80}")
                print(f"코인: {coin}")
                print(f"{'='*80}")

                # 가격 이상 탐지
                check_price_anomalies(detector, coin)

                # 거래량 이상 탐지
                check_volume_anomalies(detector, coin)

                # 종합 분석
                comprehensive_check(detector, coin)

            except Exception as e:
                print(f"❌ [{coin}] 오류: {e}")
                import traceback
                traceback.print_exc()

        print("\n")
        print_separator()
        print("✅ 이상 탐지 완료!")
        print_separator()
        print("\n💡 팁:")
        print("  - MODE를 'continuous'로 변경하면 실시간 모니터링을 할 수 있습니다")
        print("  - CHECK_INTERVAL로 체크 주기를 조정할 수 있습니다 (기본 300초)")
        print("  - COINS 리스트에 모니터링할 코인을 추가/제거할 수 있습니다")


if __name__ == "__main__":
    main()