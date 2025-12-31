"""파라미터 최적화 예제 스크립트

이 스크립트는 특정 전략의 파라미터를 최적화하는 방법을 보여줍니다.
"""
import sys
import os

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.parameter_optimizer import ParameterOptimizer
from app.services.bithumb_api import BithumbAPI
import json


def main():
    """메인 함수"""
    # API 키 설정 (실제 키로 변경하세요)
    API_KEY = ""  # Bithumb API 키
    API_SECRET = ""  # Bithumb API 시크릿

    if not API_KEY or not API_SECRET:
        print("⚠️ API 키와 시크릿을 설정해주세요!")
        print("이 스크립트 상단의 API_KEY와 API_SECRET 변수를 수정하세요.")
        return

    # 최적화 설정
    STRATEGY_TYPE = "bollinger"  # moving_average, rsi, bollinger, macd, stochastic
    COIN = "XRP"
    N_TRIALS = 50  # 최적화 시도 횟수 (많을수록 정확하지만 느림)
    DAYS_BACK = 90  # 백테스팅 기간 (일)
    INITIAL_BALANCE = 100000  # 초기 자금 (KRW)

    print("="*80)
    print("빗썸 자동매매 파라미터 최적화")
    print("="*80)
    print(f"전략 타입: {STRATEGY_TYPE}")
    print(f"코인: {COIN}")
    print(f"시도 횟수: {N_TRIALS}")
    print(f"백테스팅 기간: {DAYS_BACK}일")
    print(f"초기 자금: {INITIAL_BALANCE:,}원")
    print("="*80)
    print()

    # API 인스턴스 생성
    api = BithumbAPI(api_key=API_KEY, api_secret=API_SECRET)

    # 최적화 실행
    print("최적화를 시작합니다... (몇 분 소요될 수 있습니다)")
    print()

    optimizer = ParameterOptimizer(api)

    try:
        result = optimizer.optimize_strategy(
            strategy_type=STRATEGY_TYPE,
            coin=COIN,
            n_trials=N_TRIALS,
            initial_balance=INITIAL_BALANCE,
            days_back=DAYS_BACK
        )

        # 결과 출력
        print()
        print("="*80)
        print("최적화 완료!")
        print("="*80)
        print()

        print("📊 최적 파라미터:")
        print(json.dumps(result["best_params"], indent=2, ensure_ascii=False))
        print()

        print("📈 성과 지표:")
        perf = result["performance"]
        print(f"  - 샤프 비율: {result['sharpe_ratio']:.4f}")
        print(f"  - 총 수익률: {perf['total_return']:.2f}%")
        print(f"  - 최대 낙폭: {perf['max_drawdown']:.2f}%")
        print(f"  - 승률: {perf['win_rate']:.2f}%")
        print(f"  - 거래 횟수: {perf['num_trades']}회")
        print()

        print("💡 다음 단계:")
        print("  1. 위 파라미터를 전략 설정에 적용하세요")
        print("  2. 소액으로 실전 테스트를 진행하세요")
        print("  3. 정기적으로 성과를 모니터링하세요")
        print("  4. 시장 상황 변화 시 재최적화를 고려하세요")
        print()

        # 결과를 파일로 저장
        output_file = f"optimization_result_{STRATEGY_TYPE}_{COIN}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        print(f"✅ 결과가 {output_file}에 저장되었습니다.")

    except Exception as e:
        print(f"❌ 최적화 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()