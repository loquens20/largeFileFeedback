"""
통합 LLM 대용량 파일 처리 파이프라인
- 전처리 → 청킹 → LLM 처리
- 일시정지/재개 기능
- 실시간 비용 추적
- 진행률 표시
"""

import os
import json
import time
from typing import List, Dict, Any, Optional, Callable
from pathlib import Path
from tqdm import tqdm

from llm_large_file_processor import (
    LargeFileProcessor, ChunkInfo, ProcessingState, ModelPricing
)
from document_preprocessor import DocumentPreprocessor, ExtractedContent


class IntegratedProcessor:
    """통합 처리 파이프라인"""

    def __init__(self,
                 api_client: Any = None,  # LLM API 클라이언트
                 state_dir: str = "./processing_states",
                 chunk_dir: str = "./chunks"):
        """
        Args:
            api_client: LLM API 클라이언트 (예: Anthropic, OpenAI)
            state_dir: 진행 상황 저장 디렉토리
            chunk_dir: 청크 파일 저장 디렉토리
        """
        self.file_processor = LargeFileProcessor(state_dir)
        self.preprocessor = DocumentPreprocessor()
        self.api_client = api_client
        self.chunk_dir = Path(chunk_dir)
        self.chunk_dir.mkdir(exist_ok=True)

        self.pause_requested = False

    def preprocess_and_chunk(self,
                            file_path: str,
                            chunk_size: int = 80000,  # ~40k 토큰
                            overlap: int = 4000) -> List[ChunkInfo]:
        """
        1단계: 파일 전처리 및 청킹
        - 문서에서 텍스트/이미지 추출
        - 청크로 분할
        - 디스크에 저장
        """
        print("\n" + "="*60)
        print("1단계: 파일 전처리 및 청킹")
        print("="*60)

        # 파일 해시 계산
        file_hash = self.file_processor.calculate_file_hash(file_path)
        chunk_file = self.chunk_dir / f"{file_hash}_chunks.json"

        # 기존 청크 확인
        if chunk_file.exists():
            print(f"📂 기존 청크 파일 발견: {chunk_file}")
            with open(chunk_file, 'r', encoding='utf-8') as f:
                chunk_data = json.load(f)

            chunks = [ChunkInfo(**c) for c in chunk_data]
            print(f"✓ {len(chunks)}개 청크 로드 완료")
            return chunks

        # 새로 추출
        print("\n📄 문서 내용 추출 중...")
        extracted = self.preprocessor.extract_content(file_path)

        # 청크 생성
        print("\n🔨 청크 생성 중...")
        chunks = self._create_smart_chunks(extracted, chunk_size, overlap)

        # 청크 저장
        chunk_data = [
            {
                'index': c.index,
                'content_type': c.content_type,
                'text_content': c.text_content,
                'image_data': c.image_data,
                'token_estimate': c.token_estimate,
                'original_position': c.original_position
            }
            for c in chunks
        ]

        with open(chunk_file, 'w', encoding='utf-8') as f:
            json.dump(chunk_data, f, indent=2, ensure_ascii=False)

        print(f"✓ 청크 저장 완료: {chunk_file}")
        print(f"   총 {len(chunks)}개 청크 생성")

        return chunks

    def _create_smart_chunks(self,
                            contents: List[ExtractedContent],
                            chunk_size: int,
                            overlap: int) -> List[ChunkInfo]:
        """스마트 청킹: 텍스트와 이미지를 적절히 분할"""
        chunks = []
        current_text = []
        current_images = []
        current_size = 0
        chunk_index = 0
        start_position = 0

        for content in contents:
            if content.content_type == 'text':
                text_size = len(content.data)

                # 청크 크기 초과 시 새 청크 생성
                if current_size + text_size > chunk_size and current_text:
                    chunks.append(self._finalize_chunk(
                        chunk_index, current_text, current_images, start_position
                    ))
                    chunk_index += 1

                    # 오버랩 처리
                    if current_text:
                        overlap_text = current_text[-1][-overlap:]
                        current_text = [overlap_text]
                        current_size = len(overlap_text)
                    else:
                        current_text = []
                        current_size = 0

                    current_images = []
                    start_position = content.position

                current_text.append(content.data)
                current_size += text_size

            elif content.content_type == 'image':
                current_images.append({
                    'position': content.position,
                    'data': content.data,
                    'format': 'png'
                })
                # 이미지는 약 1500 토큰으로 계산
                current_size += 3000  # 문자 단위로 환산

        # 마지막 청크
        if current_text or current_images:
            chunks.append(self._finalize_chunk(
                chunk_index, current_text, current_images, start_position
            ))

        return chunks

    def _finalize_chunk(self,
                       index: int,
                       texts: List[str],
                       images: List[Dict],
                       start_position: int) -> ChunkInfo:
        """청크 완성"""
        text_content = '\n\n'.join(texts) if texts else None
        image_data = images if images else None

        # 콘텐츠 타입 결정
        if text_content and image_data:
            content_type = 'mixed'
        elif image_data:
            content_type = 'image'
        else:
            content_type = 'text'

        # 토큰 예측
        token_estimate = 0
        if text_content:
            token_estimate += len(text_content) // 2
        if image_data:
            token_estimate += len(image_data) * 1500

        return ChunkInfo(
            index=index,
            content_type=content_type,
            text_content=text_content,
            image_data=image_data,
            token_estimate=token_estimate,
            original_position=start_position
        )

    def process_file(self,
                    file_path: str,
                    system_prompt: str,
                    user_prompt_template: str,
                    model: str = 'claude-haiku-4',
                    output_tokens: int = 1000,
                    auto_confirm: bool = False) -> ProcessingState:
        """
        2단계: 파일 처리 실행

        Args:
            file_path: 처리할 파일
            system_prompt: 시스템 프롬프트
            user_prompt_template: 청크별 프롬프트 템플릿 (예: "{chunk_text}")
            model: 사용할 모델
            output_tokens: 예상 출력 토큰 수
            auto_confirm: 비용 확인 자동 승인
        """
        print("\n" + "="*60)
        print("2단계: LLM 처리 준비")
        print("="*60)

        # 1. 전처리 및 청킹
        chunks = self.preprocess_and_chunk(file_path)

        # 2. 상태 초기화 또는 로드
        state = self.file_processor.initialize_processing(file_path, model)

        # 3. 비용 예측
        cost_info = self.file_processor.estimate_remaining_cost(
            chunks, state.processed_chunks, model, output_tokens
        )

        print(f"\n💰 예상 비용 (현재 모델: {model})")
        print(f"   남은 청크: {cost_info['remaining_chunks']}개")
        print(f"   입력 토큰: {cost_info['input_tokens']:,}")
        print(f"   출력 토큰: {cost_info['output_tokens']:,}")
        print(f"   예상 비용: ${cost_info['estimated_cost']:.4f}")

        print(f"\n📊 다른 모델 비용 비교:")
        for model_name, cost in sorted(cost_info['model_comparison'].items(),
                                       key=lambda x: x[1]):
            emoji = "👈" if model_name == model else ""
            print(f"   {model_name:25s}: ${cost:8.4f} {emoji}")

        if not auto_confirm:
            print(f"\n현재 선택: {model} (${cost_info['estimated_cost']:.4f})")
            response = input("진행하시겠습니까? (y/n/모델명): ").strip()

            if response.lower() == 'n':
                print("❌ 처리 취소")
                return state
            elif response.lower() != 'y':
                # 모델 변경
                if response in ModelPricing.MODELS:
                    self.file_processor.change_model(response)
                    model = response
                    # 비용 재계산
                    cost_info = self.file_processor.estimate_remaining_cost(
                        chunks, state.processed_chunks, model, output_tokens
                    )
                    print(f"✓ 변경된 예상 비용: ${cost_info['estimated_cost']:.4f}")

        # 4. 처리 시작
        print("\n" + "="*60)
        print("3단계: LLM 처리 실행")
        print("="*60)

        self._process_chunks(
            chunks, state, system_prompt, user_prompt_template,
            model, output_tokens
        )

        return state

    def _process_chunks(self,
                       chunks: List[ChunkInfo],
                       state: ProcessingState,
                       system_prompt: str,
                       user_prompt_template: str,
                       model: str,
                       output_tokens: int):
        """청크 단위 처리"""
        start_index = state.processed_chunks

        with tqdm(total=len(chunks), initial=start_index,
                 desc="Processing chunks") as pbar:

            for i in range(start_index, len(chunks)):
                if self.pause_requested:
                    print("\n⏸️  일시정지 요청됨")
                    self.file_processor.save_state(state)
                    print("   진행 상황이 저장되었습니다.")
                    print("   나중에 다시 시작하려면 같은 파일로 다시 실행하세요.")
                    break

                chunk = chunks[i]

                try:
                    # API 호출
                    result = self._call_llm_api(
                        chunk, system_prompt, user_prompt_template,
                        model, output_tokens
                    )

                    # 결과 저장
                    state.results.append({
                        'chunk_index': i,
                        'response': result['response'],
                        'input_tokens': result['input_tokens'],
                        'output_tokens': result['output_tokens'],
                        'cost': result['cost']
                    })

                    # 상태 업데이트
                    state.processed_chunks = i + 1
                    state.total_cost += result['cost']

                    # 주기적 저장 (10청크마다)
                    if (i + 1) % 10 == 0:
                        self.file_processor.save_state(state)

                    pbar.set_postfix({
                        'cost': f"${state.total_cost:.4f}",
                        'chunk': f"{i+1}/{len(chunks)}"
                    })
                    pbar.update(1)

                except Exception as e:
                    print(f"\n❌ 오류 발생 (청크 {i}): {e}")
                    self.file_processor.save_state(state)
                    print("   진행 상황이 저장되었습니다.")
                    raise

        # 최종 저장
        self.file_processor.save_state(state)
        print(f"\n✅ 처리 완료!")
        print(f"   총 비용: ${state.total_cost:.4f}")
        print(f"   처리된 청크: {state.processed_chunks}/{len(chunks)}")

    def _call_llm_api(self,
                     chunk: ChunkInfo,
                     system_prompt: str,
                     user_prompt_template: str,
                     model: str,
                     max_output_tokens: int) -> Dict[str, Any]:
        """
        실제 LLM API 호출

        Note: 이 메서드는 사용하는 API에 맞게 수정 필요
        """
        if self.api_client is None:
            # 데모 모드: 실제 API 호출 없이 시뮬레이션
            time.sleep(0.1)  # API 호출 시뮬레이션
            return {
                'response': f"[Demo] Processed chunk {chunk.index}",
                'input_tokens': chunk.token_estimate,
                'output_tokens': 500,
                'cost': ModelPricing.estimate_cost(model, chunk.token_estimate, 500)
            }

        # 실제 API 호출 예시 (Anthropic Claude)
        # 프롬프트 준비
        if chunk.text_content:
            content = user_prompt_template.format(chunk_text=chunk.text_content)
        else:
            content = "이미지를 분석해주세요."

        messages = [{"role": "user", "content": content}]

        # 이미지가 있는 경우 추가
        if chunk.image_data:
            image_contents = []
            for img in chunk.image_data:
                image_contents.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": img['data']
                    }
                })
            # 이미지와 텍스트를 함께 보냄
            messages = [{
                "role": "user",
                "content": image_contents + [{"type": "text", "text": content}]
            }]

        try:
            # Anthropic API 호출
            if hasattr(self.api_client, 'messages'):
                response = self.api_client.messages.create(
                    model=model,
                    max_tokens=max_output_tokens,
                    system=system_prompt,
                    messages=messages
                )

                return {
                    'response': response.content[0].text,
                    'input_tokens': response.usage.input_tokens,
                    'output_tokens': response.usage.output_tokens,
                    'cost': ModelPricing.estimate_cost(
                        model,
                        response.usage.input_tokens,
                        response.usage.output_tokens
                    )
                }
            # OpenAI API 호출
            elif hasattr(self.api_client, 'chat'):
                response = self.api_client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        *messages
                    ],
                    max_tokens=max_output_tokens
                )

                return {
                    'response': response.choices[0].message.content,
                    'input_tokens': response.usage.prompt_tokens,
                    'output_tokens': response.usage.completion_tokens,
                    'cost': ModelPricing.estimate_cost(
                        model,
                        response.usage.prompt_tokens,
                        response.usage.completion_tokens
                    )
                }
        except Exception as e:
            print(f"API 호출 오류: {e}")
            raise

    def request_pause(self):
        """일시정지 요청"""
        self.pause_requested = True

    def export_results(self, state: ProcessingState, output_path: str):
        """결과를 파일로 내보내기"""
        output_data = {
            'file': state.file_path,
            'model': state.current_model,
            'total_cost': state.total_cost,
            'processed_chunks': state.processed_chunks,
            'total_chunks': state.total_chunks,
            'created_at': state.created_at,
            'updated_at': state.updated_at,
            'results': state.results
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        print(f"📁 결과 저장: {output_path}")


# 사용 예제
if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════╗
║  대용량 파일 LLM 처리 시스템                                  ║
║  - 31MB+ 파일 지원                                           ║
║  - 일시정지/재개                                             ║
║  - 실시간 비용 추적                                          ║
╚══════════════════════════════════════════════════════════════╝
    """)

    # 데모 모드 (API 클라이언트 없이)
    processor = IntegratedProcessor(api_client=None)

    print("\n사용 방법:")
    print("1. API 클라이언트 설정 (예: Anthropic, OpenAI)")
    print("2. processor.process_file() 호출")
    print("3. 일시정지: processor.request_pause()")
    print("4. 재개: 같은 파일로 다시 실행")
    print("\n필요한 패키지:")
    print("- python-docx, PyMuPDF, python-pptx, openpyxl")
    print("- anthropic 또는 openai (API 클라이언트)")
    print("- tqdm, Pillow")
