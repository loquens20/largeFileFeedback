# 빠른 시작 가이드

## 1. 설치

```bash
# 리포지토리 클론 (또는 파일 다운로드)
cd largeFileFeedback

# 기본 패키지 설치
pip install tqdm Pillow

# 선택: 문서 처리 패키지 (필요한 것만 설치)
pip install python-docx PyMuPDF python-pptx openpyxl

# 선택: API 클라이언트
pip install anthropic  # 또는 openai
```

## 2. 데모 실행 (API 키 불필요)

```bash
# 데모 모드로 시스템 테스트
python demo.py
```

메뉴에서 `1`을 선택하면 35MB 데모 파일이 자동 생성되고 처리됩니다.

## 3. 실제 파일 처리

### 방법 A: CLI 사용

```bash
# API 키 설정
export ANTHROPIC_API_KEY="your-api-key-here"

# 파일 처리
python cli_processor.py process your_document.pdf \
  --prompt "이 문서의 핵심 내용을 요약해주세요" \
  --model claude-haiku-4

# Ctrl+C로 중단 가능
# 재개:
python cli_processor.py resume your_document.pdf
```

### 방법 B: Python 스크립트

```python
from integrated_processor import IntegratedProcessor
from anthropic import Anthropic
import os

# API 클라이언트
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# 프로세서
processor = IntegratedProcessor(api_client=client)

# 처리
state = processor.process_file(
    file_path="your_document.pdf",
    system_prompt="당신은 문서 분석 전문가입니다.",
    user_prompt_template="다음 내용을 요약: {chunk_text}",
    model="claude-haiku-4",
    output_tokens=1000
)

# 결과 저장
processor.export_results(state, "results.json")
```

## 4. 비용 최적화 팁

### 가장 저렴한 모델로 시작

```bash
python cli_processor.py process document.pdf \
  --model gpt-4o-mini \
  --prompt "요약해주세요"
```

### 처리 중 모델 변경

```bash
# 시작
python cli_processor.py process document.pdf --model claude-haiku-4

# Ctrl+C로 중단

# 더 저렴한 모델로 재개
python cli_processor.py resume document.pdf --model gpt-4o-mini
```

### 모델별 비용 비교 (1M 입력 토큰, 100K 출력 토큰 기준)

- **gpt-4o-mini**: $0.21 ⭐ (가장 저렴)
- **claude-haiku-4**: $1.20
- **gpt-4o**: $3.50
- **claude-sonnet-4**: $4.50
- **claude-opus-4**: $22.50

## 5. 일반적인 워크플로우

### 단계 1: 저렴한 모델로 빠른 초안

```bash
python cli_processor.py process large_document.pdf \
  --model gpt-4o-mini \
  --prompt "핵심 요약" \
  --output draft_results.json
```

### 단계 2: 결과 검토

```python
import json

with open("draft_results.json") as f:
    data = json.load(f)

# 첫 번째 청크 확인
print(data['results'][0]['response'])
```

### 단계 3: 필요시 고품질 모델로 재처리

```bash
python cli_processor.py process large_document.pdf \
  --model claude-sonnet-4 \
  --prompt "상세 분석" \
  --output detailed_results.json
```

## 6. 문제 해결

### 메모리 부족

```bash
# 더 작은 청크 사용
# integrated_processor.py 수정 또는 코드에서:
chunks = processor.preprocess_and_chunk(
    file_path="document.pdf",
    chunk_size=50000  # 기본: 80000
)
```

### API 속도 제한

처리가 자동으로 진행 상황을 저장하므로:
1. 오류 발생 시 자동 저장됨
2. `resume` 명령으로 재개
3. 일정 시간 대기 후 재개

```bash
sleep 60  # 1분 대기
python cli_processor.py resume document.pdf
```

### 특정 파일 형식 오류

```bash
# 필요한 패키지 설치
pip install python-docx      # DOCX용
pip install PyMuPDF          # PDF용
pip install python-pptx      # PPTX용
pip install openpyxl         # XLSX용
```

## 7. 고급 기능

### 이미지가 포함된 문서 처리

이미지는 자동으로 감지되고 LLM에 전송됩니다:

```python
processor.process_file(
    file_path="presentation_with_images.pptx",
    system_prompt="슬라이드와 이미지를 분석하세요",
    user_prompt_template="이 슬라이드의 내용을 설명: {chunk_text}",
    model="claude-sonnet-4"  # vision 지원 모델
)
```

### 결과 후처리

```python
import json

with open("results.json") as f:
    data = json.load(f)

# 전체 응답 결합
full_text = "\n\n".join([
    f"## 청크 {r['chunk_index']}\n{r['response']}"
    for r in data['results']
])

# 마크다운 파일로 저장
with open("summary.md", "w") as f:
    f.write(full_text)

print(f"총 비용: ${data['total_cost']:.2f}")
print(f"처리 청크: {data['processed_chunks']}/{data['total_chunks']}")
```

## 8. 실전 예제

### 100MB PDF 연구 논문 요약

```bash
# 1단계: 청크 생성 및 비용 예측 (API 호출 없음)
python -c "
from integrated_processor import IntegratedProcessor
p = IntegratedProcessor()
chunks = p.preprocess_and_chunk('paper.pdf')
print(f'청크 수: {len(chunks)}')
"

# 2단계: 가장 저렴한 모델로 처리
python cli_processor.py process paper.pdf \
  --model gpt-4o-mini \
  --prompt "이 논문의 핵심 기여를 3-5문장으로 요약" \
  --output paper_summary.json

# 3단계: 결과 확인 후 필요시 재처리
python cli_processor.py process paper.pdf \
  --model claude-sonnet-4 \
  --prompt "논문의 방법론을 자세히 설명" \
  --output paper_detailed.json
```

## 지원

- 문제가 발생하면 `python cli_processor.py status`로 상태 확인
- 데모 모드로 테스트: `python demo.py`
- 모든 진행 상황은 자동 저장되며 언제든지 재개 가능

**즐거운 처리 되세요! 🚀**
