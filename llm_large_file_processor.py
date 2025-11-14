"""
대용량 파일(31MB+) LLM 처리 시스템
- 청크 단위 처리
- 진행 상황 저장/복원
- 비용 예측
- 일시정지/재개 기능
"""

import os
import json
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import base64

@dataclass
class ProcessingState:
    """처리 상태 저장"""
    file_path: str
    file_hash: str
    total_chunks: int
    processed_chunks: int
    current_model: str
    total_cost: float
    results: List[Dict[str, Any]]
    created_at: str
    updated_at: str

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict):
        return cls(**data)


@dataclass
class ChunkInfo:
    """청크 정보"""
    index: int
    content_type: str  # 'text', 'image', 'mixed'
    text_content: Optional[str]
    image_data: Optional[List[Dict[str, Any]]]  # base64 인코딩된 이미지와 위치 정보
    token_estimate: int
    original_position: int  # 원본 파일에서의 위치


class ModelPricing:
    """모델별 가격 정보 (1M 토큰 기준)"""
    MODELS = {
        'claude-sonnet-4-5': {'input': 3.00, 'output': 15.00},
        'claude-sonnet-4': {'input': 3.00, 'output': 15.00},
        'claude-opus-4': {'input': 15.00, 'output': 75.00},
        'claude-haiku-4': {'input': 0.80, 'output': 4.00},
        'gpt-4o': {'input': 2.50, 'output': 10.00},
        'gpt-4o-mini': {'input': 0.15, 'output': 0.60},
    }

    @classmethod
    def estimate_cost(cls, model: str, input_tokens: int, output_tokens: int) -> float:
        """비용 예측"""
        if model not in cls.MODELS:
            raise ValueError(f"지원하지 않는 모델: {model}")

        pricing = cls.MODELS[model]
        cost = (input_tokens / 1_000_000 * pricing['input'] +
                output_tokens / 1_000_000 * pricing['output'])
        return cost

    @classmethod
    def compare_models(cls, input_tokens: int, output_tokens: int) -> Dict[str, float]:
        """모든 모델의 비용 비교"""
        return {
            model: cls.estimate_cost(model, input_tokens, output_tokens)
            for model in cls.MODELS.keys()
        }


class LargeFileProcessor:
    """대용량 파일 처리 클래스"""

    def __init__(self, state_dir: str = "./processing_states"):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(exist_ok=True)
        self.current_state: Optional[ProcessingState] = None

    def calculate_file_hash(self, file_path: str) -> str:
        """파일 해시 계산 (진행 상황 식별용)"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def estimate_tokens(self, text: str, images: int = 0) -> int:
        """토큰 수 예측 (대략적)"""
        # 텍스트: 1 토큰 ≈ 4자 (영어 기준)
        # 한글: 1 토큰 ≈ 1.5자
        text_tokens = len(text) // 2  # 보수적 추정
        # 이미지: 약 1000-2000 토큰/이미지
        image_tokens = images * 1500
        return text_tokens + image_tokens

    def create_chunks(self,
                     file_path: str,
                     chunk_size: int = 100000,  # 약 50k 토큰
                     overlap: int = 5000) -> List[ChunkInfo]:
        """
        파일을 청크로 분할

        Args:
            file_path: 파일 경로
            chunk_size: 청크 크기 (문자 수)
            overlap: 청크 간 겹침 (문맥 유지)
        """
        # 이 메서드는 파일 형식에 따라 오버라이드 필요
        # 기본 텍스트 파일 처리
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        chunks = []
        start = 0
        index = 0

        while start < len(content):
            end = start + chunk_size
            chunk_text = content[start:end]

            chunks.append(ChunkInfo(
                index=index,
                content_type='text',
                text_content=chunk_text,
                image_data=None,
                token_estimate=self.estimate_tokens(chunk_text),
                original_position=start
            ))

            start = end - overlap
            index += 1

        return chunks

    def save_state(self, state: ProcessingState):
        """진행 상황 저장"""
        state_file = self.state_dir / f"{state.file_hash}.json"
        state.updated_at = datetime.now().isoformat()

        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(state.to_dict(), f, indent=2, ensure_ascii=False)

        print(f"✓ 진행 상황 저장됨: {state_file}")

    def load_state(self, file_path: str) -> Optional[ProcessingState]:
        """저장된 진행 상황 불러오기"""
        file_hash = self.calculate_file_hash(file_path)
        state_file = self.state_dir / f"{file_hash}.json"

        if not state_file.exists():
            return None

        with open(state_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        return ProcessingState.from_dict(data)

    def initialize_processing(self,
                            file_path: str,
                            model: str = 'claude-haiku-4') -> ProcessingState:
        """처리 초기화"""
        file_hash = self.calculate_file_hash(file_path)

        # 기존 상태 확인
        existing_state = self.load_state(file_path)
        if existing_state:
            print(f"📂 기존 진행 상황 발견: {existing_state.processed_chunks}/{existing_state.total_chunks} 청크 처리 완료")
            print(f"   현재 모델: {existing_state.current_model}")
            print(f"   누적 비용: ${existing_state.total_cost:.4f}")

            response = input("계속 진행하시겠습니까? (y/n): ")
            if response.lower() == 'y':
                self.current_state = existing_state
                return existing_state

        # 새로운 처리 시작
        print("📄 파일 청크 분할 중...")
        chunks = self.create_chunks(file_path)

        state = ProcessingState(
            file_path=file_path,
            file_hash=file_hash,
            total_chunks=len(chunks),
            processed_chunks=0,
            current_model=model,
            total_cost=0.0,
            results=[],
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )

        self.current_state = state
        self.save_state(state)

        return state

    def estimate_remaining_cost(self,
                               chunks: List[ChunkInfo],
                               start_index: int,
                               model: str,
                               output_tokens_per_chunk: int = 1000) -> Dict[str, Any]:
        """남은 처리 비용 예측"""
        remaining_chunks = chunks[start_index:]
        total_input_tokens = sum(chunk.token_estimate for chunk in remaining_chunks)
        total_output_tokens = len(remaining_chunks) * output_tokens_per_chunk

        cost = ModelPricing.estimate_cost(model, total_input_tokens, total_output_tokens)

        # 다른 모델과 비교
        model_comparison = ModelPricing.compare_models(total_input_tokens, total_output_tokens)

        return {
            'remaining_chunks': len(remaining_chunks),
            'input_tokens': total_input_tokens,
            'output_tokens': total_output_tokens,
            'estimated_cost': cost,
            'model_comparison': model_comparison
        }

    def change_model(self, new_model: str):
        """처리 중 모델 변경"""
        if self.current_state is None:
            raise ValueError("처리 상태가 초기화되지 않았습니다.")

        old_model = self.current_state.current_model
        self.current_state.current_model = new_model
        self.save_state(self.current_state)

        print(f"🔄 모델 변경: {old_model} → {new_model}")


# 사용 예제
if __name__ == "__main__":
    processor = LargeFileProcessor()

    # 비용 예측 예제
    print("\n" + "="*60)
    print("모델별 비용 비교 (100만 입력 토큰, 10만 출력 토큰)")
    print("="*60)
    comparison = ModelPricing.compare_models(1_000_000, 100_000)
    for model, cost in sorted(comparison.items(), key=lambda x: x[1]):
        print(f"{model:25s}: ${cost:8.2f}")
