#!/usr/bin/env python3
"""
대용량 파일 처리 데모
API 클라이언트 없이도 시스템 동작 확인 가능
"""

import os
import time
from pathlib import Path
from integrated_processor import IntegratedProcessor
from llm_large_file_processor import ModelPricing


def create_demo_file(size_mb: int = 35) -> str:
    """데모용 대용량 텍스트 파일 생성"""
    demo_file = "demo_large_file.txt"

    if Path(demo_file).exists():
        print(f"✓ 기존 데모 파일 사용: {demo_file}")
        return demo_file

    print(f"📝 {size_mb}MB 데모 파일 생성 중...")

    # 샘플 텍스트
    sample_text = """
이것은 대용량 파일 처리를 테스트하기 위한 샘플 텍스트입니다.
실제 환경에서는 연구 논문, 기술 문서, 계약서 등이 될 수 있습니다.

주요 특징:
1. 31MB를 초과하는 파일 처리
2. 일시정지 및 재개 기능
3. 실시간 비용 추적
4. 모델 변경 지원

이 시스템은 다양한 문서 형식을 지원합니다:
- Microsoft Word (.docx)
- PDF 문서 (.pdf)
- PowerPoint (.pptx)
- Excel (.xlsx)
- 일반 텍스트 (.txt)

""" * 100

    target_size = size_mb * 1024 * 1024
    current_size = 0

    with open(demo_file, 'w', encoding='utf-8') as f:
        while current_size < target_size:
            f.write(sample_text)
            current_size += len(sample_text.encode('utf-8'))

    actual_size = os.path.getsize(demo_file) / (1024 * 1024)
    print(f"✓ 데모 파일 생성 완료: {actual_size:.2f}MB")

    return demo_file


def demo_basic_processing():
    """기본 처리 데모"""
    print("\n" + "="*70)
    print("데모 1: 기본 파일 처리")
    print("="*70)

    # 데모 파일 생성
    demo_file = create_demo_file(35)

    # 프로세서 초기화 (API 클라이언트 없음 = 데모 모드)
    processor = IntegratedProcessor(api_client=None)

    print("\n📊 비용 예측 중...")

    # 청크 생성
    chunks = processor.preprocess_and_chunk(demo_file, chunk_size=100000)

    # 비용 예측
    total_input_tokens = sum(chunk.token_estimate for chunk in chunks)
    output_per_chunk = 1000
    total_output_tokens = len(chunks) * output_per_chunk

    print(f"\n파일 정보:")
    print(f"  - 파일 크기: {os.path.getsize(demo_file) / (1024*1024):.2f}MB")
    print(f"  - 총 청크 수: {len(chunks)}")
    print(f"  - 예상 입력 토큰: {total_input_tokens:,}")
    print(f"  - 예상 출력 토큰: {total_output_tokens:,}")

    print(f"\n💰 모델별 예상 비용:")
    costs = ModelPricing.compare_models(total_input_tokens, total_output_tokens)

    for model, cost in sorted(costs.items(), key=lambda x: x[1]):
        savings = costs['claude-opus-4'] - cost if model != 'claude-opus-4' else 0
        savings_pct = (savings / costs['claude-opus-4'] * 100) if savings > 0 else 0

        print(f"  {model:25s}: ${cost:8.2f}", end="")
        if savings > 0:
            print(f"  (💰 ${savings:.2f} 절약, {savings_pct:.1f}%)", end="")
        print()

    # 처리 시작 (데모 모드)
    print(f"\n▶️  처리 시작 (데모 모드 - 실제 API 호출 없음)")
    print("   Ctrl+C를 눌러 일시정지할 수 있습니다.")

    state = processor.process_file(
        file_path=demo_file,
        system_prompt="문서 분석 전문가",
        user_prompt_template="다음 내용을 요약: {chunk_text}",
        model="claude-haiku-4",
        output_tokens=1000,
        auto_confirm=True  # 데모에서는 자동 확인
    )

    print(f"\n✅ 처리 완료!")
    print(f"   총 비용 (데모): ${state.total_cost:.4f}")
    print(f"   처리된 청크: {state.processed_chunks}/{state.total_chunks}")


def demo_pause_resume():
    """일시정지/재개 데모"""
    print("\n" + "="*70)
    print("데모 2: 일시정지 및 재개")
    print("="*70)

    demo_file = "demo_large_file.txt"

    if not Path(demo_file).exists():
        print("❌ 데모 파일이 없습니다. 먼저 데모 1을 실행하세요.")
        return

    processor = IntegratedProcessor(api_client=None)

    # 기존 상태 확인
    state = processor.file_processor.load_state(demo_file)

    if state is None:
        print("❌ 저장된 처리 상태가 없습니다.")
        print("   먼저 데모 1을 실행하고 Ctrl+C로 중단하세요.")
        return

    print(f"\n📂 저장된 상태 발견:")
    print(f"   진행: {state.processed_chunks}/{state.total_chunks} 청크")
    print(f"   모델: {state.current_model}")
    print(f"   누적 비용: ${state.total_cost:.4f}")

    # 모델 변경 데모
    print(f"\n🔄 모델 변경: {state.current_model} → gpt-4o-mini")
    processor.file_processor.change_model("gpt-4o-mini")

    # 남은 비용 예측
    chunks = processor.preprocess_and_chunk(demo_file)
    remaining_cost = processor.file_processor.estimate_remaining_cost(
        chunks, state.processed_chunks, "gpt-4o-mini", 1000
    )

    print(f"\n💰 남은 처리 예상 비용:")
    print(f"   남은 청크: {remaining_cost['remaining_chunks']}")
    print(f"   예상 비용: ${remaining_cost['estimated_cost']:.4f}")

    print(f"\n▶️  처리 재개...")

    # 재개
    processor._process_chunks(
        chunks=chunks,
        state=state,
        system_prompt="문서 분석",
        user_prompt_template="{chunk_text}",
        model="gpt-4o-mini",
        output_tokens=1000
    )

    print(f"\n✅ 완료!")


def demo_model_comparison():
    """모델 비교 데모"""
    print("\n" + "="*70)
    print("데모 3: 다양한 시나리오별 최적 모델")
    print("="*70)

    scenarios = [
        {
            'name': '소규모 요약 (10MB, 간단)',
            'input_tokens': 500_000,
            'output_tokens': 50_000
        },
        {
            'name': '중규모 번역 (50MB, 중간)',
            'input_tokens': 2_500_000,
            'output_tokens': 2_500_000
        },
        {
            'name': '대규모 분석 (100MB, 복잡)',
            'input_tokens': 5_000_000,
            'output_tokens': 500_000
        }
    ]

    for scenario in scenarios:
        print(f"\n📊 {scenario['name']}")
        print(f"   입력: {scenario['input_tokens']:,} 토큰")
        print(f"   출력: {scenario['output_tokens']:,} 토큰")
        print()

        costs = ModelPricing.compare_models(
            scenario['input_tokens'],
            scenario['output_tokens']
        )

        sorted_costs = sorted(costs.items(), key=lambda x: x[1])
        cheapest = sorted_costs[0]

        for model, cost in sorted_costs:
            marker = "👈 추천" if model == cheapest[0] else ""
            time_estimate = scenario['input_tokens'] / 1000  # 대략적 시간(초)

            print(f"   {model:25s}: ${cost:8.2f}  {marker}")

        print(f"\n   💡 권장: {cheapest[0]} (${cheapest[1]:.2f})")


def demo_interactive():
    """대화형 데모"""
    print("\n" + "="*70)
    print("대화형 데모")
    print("="*70)

    while True:
        print("\n다음 중 선택하세요:")
        print("1. 기본 처리 데모")
        print("2. 일시정지/재개 데모")
        print("3. 모델 비교")
        print("4. 처리 상태 확인")
        print("5. 종료")

        choice = input("\n선택 (1-5): ").strip()

        if choice == '1':
            demo_basic_processing()
        elif choice == '2':
            demo_pause_resume()
        elif choice == '3':
            demo_model_comparison()
        elif choice == '4':
            processor = IntegratedProcessor()
            state_files = list(processor.file_processor.state_dir.glob("*.json"))

            if not state_files:
                print("\n저장된 상태가 없습니다.")
            else:
                print(f"\n저장된 처리 상태: {len(state_files)}개")
                for sf in state_files:
                    import json
                    with open(sf) as f:
                        data = json.load(f)
                    print(f"\n  📄 {Path(data['file_path']).name}")
                    print(f"     진행: {data['processed_chunks']}/{data['total_chunks']}")
                    print(f"     비용: ${data['total_cost']:.4f}")
        elif choice == '5':
            print("\n👋 종료합니다.")
            break
        else:
            print("\n❌ 잘못된 선택입니다.")


if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║      대용량 파일 LLM 처리 시스템 - 데모                       ║
║                                                              ║
║  • 31MB+ 파일 처리                                           ║
║  • 일시정지/재개 (Ctrl+C)                                    ║
║  • 비용 최적화                                               ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """)

    print("\n이 데모는 API 클라이언트 없이 실행됩니다.")
    print("실제 사용 시에는 ANTHROPIC_API_KEY 또는 OPENAI_API_KEY를 설정하세요.")

    demo_interactive()
