#!/usr/bin/env python3
"""
실전 사용 예제 모음
다양한 시나리오에 대한 구체적인 코드 예제
"""

import os
from integrated_processor import IntegratedProcessor
from llm_large_file_processor import ModelPricing


def example_1_simple_summary():
    """예제 1: 가장 간단한 문서 요약"""
    print("\n" + "="*70)
    print("예제 1: 간단한 문서 요약")
    print("="*70)

    from anthropic import Anthropic

    processor = IntegratedProcessor(
        api_client=Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    )

    state = processor.process_file(
        file_path="document.pdf",
        system_prompt="당신은 요약 전문가입니다.",
        user_prompt_template="다음 내용을 3-5 문장으로 요약:\n{chunk_text}",
        model="claude-haiku-4",
        output_tokens=500
    )

    print(f"완료! 총 비용: ${state.total_cost:.2f}")


def example_2_cost_optimization():
    """예제 2: 비용 최적화 전략"""
    print("\n" + "="*70)
    print("예제 2: 비용 최적화")
    print("="*70)

    processor = IntegratedProcessor(api_client=None)  # 데모 모드

    # 1단계: 청크 생성 (무료)
    print("\n1단계: 청크 생성 및 비용 예측")
    chunks = processor.preprocess_and_chunk("large_file.pdf")

    # 2단계: 비용 비교
    print("\n2단계: 모델별 비용 비교")
    total_tokens = sum(c.token_estimate for c in chunks)
    output_per_chunk = 1000

    costs = ModelPricing.compare_models(
        total_tokens,
        len(chunks) * output_per_chunk
    )

    cheapest = min(costs.items(), key=lambda x: x[1])
    most_expensive = max(costs.items(), key=lambda x: x[1])

    print(f"\n가장 저렴: {cheapest[0]} (${cheapest[1]:.2f})")
    print(f"가장 비싼: {most_expensive[0]} (${most_expensive[1]:.2f})")
    print(f"절약 가능: ${most_expensive[1] - cheapest[1]:.2f} "
          f"({(most_expensive[1] - cheapest[1]) / most_expensive[1] * 100:.1f}%)")

    # 3단계: 저렴한 모델로 처리 결정
    print(f"\n3단계: {cheapest[0]} 모델로 처리 시작")
    print("(실제 API 키가 있다면 여기서 process_file 호출)")


def example_3_progressive_quality():
    """예제 3: 점진적 품질 향상"""
    print("\n" + "="*70)
    print("예제 3: 점진적 품질 향상")
    print("="*70)

    processor = IntegratedProcessor(api_client=None)

    # Phase 1: 빠른 초안
    print("\nPhase 1: 빠른 초안 (gpt-4o-mini)")
    state1 = processor.process_file(
        file_path="test_small.txt",
        system_prompt="간단히 요약하세요",
        user_prompt_template="{chunk_text}",
        model="gpt-4o-mini",
        output_tokens=300,
        auto_confirm=True
    )

    print(f"Phase 1 완료. 비용: ${state1.total_cost:.4f}")

    # 결과 검토 (실제로는 사용자가 확인)
    print("\n결과를 검토합니다...")
    print("만족스럽지 않다면 Phase 2로 이동")

    # Phase 2: 고품질 분석 (필요시)
    print("\nPhase 2: 고품질 분석 (claude-sonnet-4)")
    state2 = processor.process_file(
        file_path="test_small.txt",
        system_prompt="자세하고 정확하게 분석하세요",
        user_prompt_template="{chunk_text}",
        model="claude-sonnet-4",
        output_tokens=1000,
        auto_confirm=True
    )

    print(f"Phase 2 완료. 비용: ${state2.total_cost:.4f}")
    print(f"총 비용: ${state1.total_cost + state2.total_cost:.4f}")


def example_4_pause_resume():
    """예제 4: 일시정지 및 재개"""
    print("\n" + "="*70)
    print("예제 4: 일시정지 및 재개")
    print("="*70)

    import threading
    import time

    processor = IntegratedProcessor(api_client=None)

    def process_task():
        """백그라운드에서 실행"""
        try:
            processor.process_file(
                file_path="test_small.txt",
                system_prompt="분석",
                user_prompt_template="{chunk_text}",
                model="claude-haiku-4",
                auto_confirm=True
            )
        except Exception as e:
            print(f"처리 중 오류: {e}")

    # 스레드 시작
    print("처리 시작...")
    thread = threading.Thread(target=process_task)
    thread.start()

    # 1초 후 일시정지
    time.sleep(1)
    print("\n일시정지 요청...")
    processor.request_pause()

    # 스레드 종료 대기
    thread.join()

    print("\n일시정지 완료!")
    print("나중에 다음 명령으로 재개:")
    print("  python cli_processor.py resume test_small.txt")


def example_5_model_switching():
    """예제 5: 처리 중 모델 변경"""
    print("\n" + "="*70)
    print("예제 5: 처리 중 모델 변경")
    print("="*70)

    processor = IntegratedProcessor(api_client=None)

    # 초기 상태 확인
    state = processor.file_processor.load_state("test_small.txt")

    if state is None:
        print("먼저 처리를 시작해야 합니다:")
        print("  python cli_processor.py process test_small.txt")
        return

    print(f"현재 모델: {state.current_model}")
    print(f"진행: {state.processed_chunks}/{state.total_chunks}")
    print(f"누적 비용: ${state.total_cost:.4f}")

    # 모델 변경
    new_model = "gpt-4o-mini"
    print(f"\n모델 변경: {state.current_model} → {new_model}")

    processor.file_processor.change_model(new_model)

    # 남은 비용 예측
    chunks = processor.preprocess_and_chunk("test_small.txt")
    remaining = processor.file_processor.estimate_remaining_cost(
        chunks, state.processed_chunks, new_model, 1000
    )

    print(f"남은 예상 비용: ${remaining['estimated_cost']:.4f}")
    print("\n재개하려면:")
    print("  python cli_processor.py resume test_small.txt")


def example_6_batch_processing():
    """예제 6: 여러 파일 일괄 처리"""
    print("\n" + "="*70)
    print("예제 6: 여러 파일 일괄 처리")
    print("="*70)

    from pathlib import Path

    processor = IntegratedProcessor(api_client=None)

    # 처리할 파일 목록
    files = [
        "document1.pdf",
        "document2.docx",
        "document3.txt"
    ]

    results_summary = []

    for file_path in files:
        if not Path(file_path).exists():
            print(f"⏭️  건너뛰기: {file_path} (파일 없음)")
            continue

        print(f"\n📄 처리 중: {file_path}")

        try:
            state = processor.process_file(
                file_path=file_path,
                system_prompt="요약 전문가",
                user_prompt_template="요약: {chunk_text}",
                model="claude-haiku-4",
                output_tokens=500,
                auto_confirm=True
            )

            results_summary.append({
                'file': file_path,
                'chunks': state.processed_chunks,
                'cost': state.total_cost,
                'status': 'success'
            })

            # 결과 저장
            output_file = f"results_{Path(file_path).stem}.json"
            processor.export_results(state, output_file)

        except Exception as e:
            print(f"❌ 오류: {e}")
            results_summary.append({
                'file': file_path,
                'status': 'error',
                'error': str(e)
            })

    # 전체 요약
    print("\n" + "="*70)
    print("처리 요약")
    print("="*70)

    total_cost = sum(r.get('cost', 0) for r in results_summary)
    success_count = sum(1 for r in results_summary if r['status'] == 'success')

    print(f"\n총 {len(files)}개 파일 중 {success_count}개 성공")
    print(f"총 비용: ${total_cost:.2f}")


def example_7_custom_chunking():
    """예제 7: 커스텀 청킹 전략"""
    print("\n" + "="*70)
    print("예제 7: 커스텀 청킹 전략")
    print("="*70)

    processor = IntegratedProcessor(api_client=None)

    # 시나리오 1: 작은 청크 (더 정확한 컨텍스트)
    print("\n시나리오 1: 작은 청크 (50K 문자)")
    chunks_small = processor.preprocess_and_chunk(
        "test_small.txt",
        chunk_size=50000,
        overlap=2000
    )
    print(f"  청크 수: {len(chunks_small)}")

    # 시나리오 2: 큰 청크 (비용 절감)
    print("\n시나리오 2: 큰 청크 (150K 문자)")
    chunks_large = processor.preprocess_and_chunk(
        "test_small.txt",
        chunk_size=150000,
        overlap=5000
    )
    print(f"  청크 수: {len(chunks_large)}")

    # 비용 비교
    cost_small = len(chunks_small) * 0.01  # 예상 청크당 비용
    cost_large = len(chunks_large) * 0.01

    print(f"\n비용 예상:")
    print(f"  작은 청크: ${cost_small:.2f}")
    print(f"  큰 청크: ${cost_large:.2f}")
    print(f"  절약: ${cost_small - cost_large:.2f}")


def example_8_result_analysis():
    """예제 8: 결과 분석 및 후처리"""
    print("\n" + "="*70)
    print("예제 8: 결과 분석")
    print("="*70)

    import json
    from pathlib import Path

    # 결과 파일이 있다고 가정
    result_file = "results.json"

    if not Path(result_file).exists():
        print(f"결과 파일이 없습니다: {result_file}")
        print("먼저 파일을 처리하고 export하세요.")
        return

    with open(result_file) as f:
        data = json.load(f)

    # 기본 통계
    print("\n📊 기본 통계:")
    print(f"  파일: {data['file']}")
    print(f"  모델: {data['model']}")
    print(f"  처리 청크: {data['processed_chunks']}/{data['total_chunks']}")
    print(f"  총 비용: ${data['total_cost']:.2f}")

    # 토큰 통계
    total_input = sum(r['input_tokens'] for r in data['results'])
    total_output = sum(r['output_tokens'] for r in data['results'])

    print(f"\n📈 토큰 사용:")
    print(f"  입력: {total_input:,} 토큰")
    print(f"  출력: {total_output:,} 토큰")
    print(f"  평균 입력/청크: {total_input // len(data['results']):,}")
    print(f"  평균 출력/청크: {total_output // len(data['results']):,}")

    # 비용 분석
    avg_cost_per_chunk = data['total_cost'] / len(data['results'])

    print(f"\n💰 비용 분석:")
    print(f"  청크당 평균 비용: ${avg_cost_per_chunk:.4f}")
    print(f"  1MB당 예상 비용: ${avg_cost_per_chunk * 100:.2f}")

    # 전체 텍스트 결합
    full_text = "\n\n---\n\n".join([
        f"## 청크 {r['chunk_index'] + 1}\n\n{r['response']}"
        for r in data['results']
    ])

    # 마크다운으로 저장
    output_md = "combined_results.md"
    with open(output_md, "w", encoding="utf-8") as f:
        f.write(f"# 처리 결과: {Path(data['file']).name}\n\n")
        f.write(f"**모델**: {data['model']}\n")
        f.write(f"**비용**: ${data['total_cost']:.2f}\n\n")
        f.write("---\n\n")
        f.write(full_text)

    print(f"\n✅ 결과 저장: {output_md}")


def main():
    """메인 메뉴"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║              실전 사용 예제 모음                              ║
╚══════════════════════════════════════════════════════════════╝
    """)

    examples = {
        '1': ('간단한 문서 요약', example_1_simple_summary),
        '2': ('비용 최적화 전략', example_2_cost_optimization),
        '3': ('점진적 품질 향상', example_3_progressive_quality),
        '4': ('일시정지 및 재개', example_4_pause_resume),
        '5': ('처리 중 모델 변경', example_5_model_switching),
        '6': ('여러 파일 일괄 처리', example_6_batch_processing),
        '7': ('커스텀 청킹 전략', example_7_custom_chunking),
        '8': ('결과 분석 및 후처리', example_8_result_analysis),
    }

    while True:
        print("\n예제 선택:")
        for key, (name, _) in examples.items():
            print(f"  {key}. {name}")
        print("  q. 종료")

        choice = input("\n선택: ").strip().lower()

        if choice == 'q':
            print("\n종료합니다.")
            break

        if choice in examples:
            name, func = examples[choice]
            try:
                func()
            except Exception as e:
                print(f"\n❌ 오류 발생: {e}")
                import traceback
                traceback.print_exc()
        else:
            print("\n❌ 잘못된 선택입니다.")

        input("\n계속하려면 Enter를 누르세요...")


if __name__ == "__main__":
    main()
