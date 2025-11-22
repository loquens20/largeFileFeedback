# 대용량 파일(31MB+) LLM 처리 시스템

## 🎯 주요 기능

- ✅ **31MB 초과** 대용량 파일 처리
- 🔄 **일시정지/재개** 기능 (Ctrl+C로 언제든지 중단 가능)
- 💰 **실시간 비용 예측** 및 추적
- 🔀 **모델 변경** 기능 (처리 중간에 더 저렴한 모델로 전환 가능)
- 📄 **다양한 형식** 지원: DOCX, PDF, PPTX, XLSX, TXT
- 🖼️ **이미지 포함** 문서 처리 (텍스트와 이미지 순서 보존)

## 📦 설치

```bash
# 기본 패키지
pip install tqdm Pillow

# 문서 처리 패키지
pip install python-docx PyMuPDF python-pptx openpyxl

# API 클라이언트 (선택)
pip install anthropic  # Anthropic Claude
pip install openai     # OpenAI GPT
```

또는 한 번에:

```bash
pip install -r requirements.txt
```

## 🚀 빠른 시작

### 1. 웹 인터페이스 사용 (가장 쉬운 방법)

```bash
# Flask 및 필요한 패키지 설치
pip install -r requirements.txt

# 웹 서버 시작
python app.py
```

웹 브라우저에서 `http://localhost:5000` 접속 후:

1. 📁 **파일 선택**: TXT, PDF, DOCX, PPTX, XLSX 파일 업로드 (최대 100MB)
2. ✏️ **프롬프트 입력**: LLM에게 어떤 작업을 할지 지시
3. 🤖 **모델 선택**: Claude Haiku/Sonnet/Opus 또는 GPT-4o/mini
4. 🔑 **API 키 입력**: Anthropic 또는 OpenAI API 키 (저장되지 않음)
5. 🚀 **처리 시작**: 실시간으로 진행상황 확인
6. 📥 **결과 다운로드**: 처리 완료 후 JSON 형식으로 다운로드

**웹 인터페이스 특징:**
- 실시간 진행상황 표시
- 청크별 처리 상태 확인
- 예상 비용 자동 계산
- 사용자 친화적인 UI
- 모바일 반응형 디자인

### 2. CLI 사용

```bash
# 환경 변수 설정
export ANTHROPIC_API_KEY="your-api-key"

# 파일 처리 시작
python cli_processor.py process document.pdf \
  --prompt "이 문서를 요약해주세요" \
  --model claude-haiku-4

# 처리 중 Ctrl+C를 누르면 일시정지됩니다
# 재개하려면:
python cli_processor.py resume document.pdf

# 더 저렴한 모델로 변경하여 재개:
python cli_processor.py resume document.pdf --model gpt-4o-mini

# 처리 상태 확인
python cli_processor.py status

# 결과 내보내기
python cli_processor.py export document.pdf --output results.json
```

### 3. Python 코드로 사용

```python
from integrated_processor import IntegratedProcessor
from anthropic import Anthropic

# API 클라이언트 설정
client = Anthropic(api_key="your-api-key")

# 프로세서 초기화
processor = IntegratedProcessor(api_client=client)

# 파일 처리
state = processor.process_file(
    file_path="large_document.pdf",
    system_prompt="당신은 문서 분석 전문가입니다.",
    user_prompt_template="다음 내용을 분석하고 핵심 내용을 추출해주세요:\n\n{chunk_text}",
    model="claude-haiku-4",
    output_tokens=1000,
    auto_confirm=False  # 비용 확인 후 진행
)

# 결과 저장
processor.export_results(state, "analysis_results.json")
```

### 4. 데모 모드로 시작

API 키가 없어도 시스템을 테스트할 수 있습니다:

```bash
python demo.py
```

## 💡 실제 사용 예제

### 예제 1: 대용량 연구 논문 요약

```python
from integrated_processor import IntegratedProcessor
from anthropic import Anthropic

processor = IntegratedProcessor(
    api_client=Anthropic(api_key="your-key")
)

state = processor.process_file(
    file_path="research_paper_50mb.pdf",
    system_prompt="""당신은 학술 논문 분석 전문가입니다.
    각 섹션의 핵심 내용을 정확하게 요약하세요.""",
    user_prompt_template="""
    다음 논문 섹션을 분석하고 다음 항목을 제공하세요:
    1. 핵심 주장
    2. 주요 방법론
    3. 중요한 결과
    4. 인용할 만한 문장

    내용:
    {chunk_text}
    """,
    model="claude-sonnet-4",  # 고품질 분석
    output_tokens=2000
)
```

### 예제 2: 계약서 검토 (이미지 포함)

```python
state = processor.process_file(
    file_path="contract_with_signatures.pdf",
    system_prompt="""당신은 법률 문서 검토 전문가입니다.
    계약 조항의 위험 요소를 찾아내고 설명하세요.""",
    user_prompt_template="""
    다음 계약서 섹션을 검토하고:
    1. 잠재적 위험 조항
    2. 불명확한 표현
    3. 권장 수정사항
    을 제공하세요.

    {chunk_text}
    """,
    model="claude-opus-4",  # 정확도 최우선
    output_tokens=1500
)
```

### 예제 3: 대용량 기술 문서 번역

```python
# 먼저 저렴한 모델로 시작
state = processor.process_file(
    file_path="tech_manual_100mb.docx",
    system_prompt="당신은 기술 번역 전문가입니다.",
    user_prompt_template="다음 기술 문서를 한국어로 번역하세요:\n\n{chunk_text}",
    model="claude-haiku-4",  # 저렴한 모델로 시작
    output_tokens=3000
)

# 처리 중 Ctrl+C로 일시정지하고
# 더 고품질이 필요한 부분만 claude-sonnet-4로 재처리 가능
```

## 💰 비용 최적화 전략

### 1. 점진적 품질 향상

```python
# Phase 1: 빠른 초안 (저렴)
processor.process_file(
    file_path="document.pdf",
    model="claude-haiku-4",
    output_tokens=500
)

# 결과 확인 후 만족스럽지 않으면
# Phase 2: 품질 개선 (중간)
processor.process_file(
    file_path="document.pdf",
    model="claude-sonnet-4",
    output_tokens=1000
)
```

### 2. 청크 크기 조정으로 비용 절감

```python
# 큰 청크 = 적은 API 호출 = 낮은 비용
processor = IntegratedProcessor()
chunks = processor.preprocess_and_chunk(
    file_path="document.pdf",
    chunk_size=150000,  # 더 큰 청크 (기본: 80000)
    overlap=2000        # 적은 오버랩 (기본: 4000)
)
```

### 3. 이미지 크기 조정

```python
from document_preprocessor import DocumentPreprocessor

# 이미지 크기 제한으로 비용 절감
preprocessor = DocumentPreprocessor(
    max_image_size=(1024, 1024)  # 기본: (2048, 2048)
)
```

## 📊 모델별 가격 비교

현재 지원되는 모델 (1M 토큰 기준):

| 모델 | 입력 비용 | 출력 비용 | 권장 사용 |
|------|----------|----------|----------|
| claude-haiku-4 | $0.80 | $4.00 | 일반 작업, 초안 |
| gpt-4o-mini | $0.15 | $0.60 | 대량 처리, 단순 작업 |
| claude-sonnet-4 | $3.00 | $15.00 | 고품질 분석 |
| gpt-4o | $2.50 | $10.00 | 복잡한 추론 |
| claude-opus-4 | $15.00 | $75.00 | 최고 품질 필요 시 |

예상 비용 계산:

```bash
# 100MB PDF 파일, 약 5M 입력 토큰, 500K 출력 토큰 가정

claude-haiku-4:  $6.00 ($4.00 입력 + $2.00 출력)
gpt-4o-mini:     $1.05 ($0.75 입력 + $0.30 출력)
claude-sonnet-4: $22.50 ($15.00 입력 + $7.50 출력)
claude-opus-4:   $112.50 ($75.00 입력 + $37.50 출력)
```

## 🔧 고급 기능

### 일시정지/재개 프로그래밍 방식

```python
import threading
import time

processor = IntegratedProcessor(api_client=client)

# 별도 스레드에서 처리
def process_task():
    processor.process_file(
        file_path="document.pdf",
        system_prompt="분석 전문가",
        user_prompt_template="{chunk_text}",
        model="claude-haiku-4"
    )

thread = threading.Thread(target=process_task)
thread.start()

# 10초 후 일시정지
time.sleep(10)
processor.request_pause()
thread.join()

print("일시정지됨. 나중에 재개 가능.")
```

### 결과 후처리

```python
import json

# 처리 완료 후 결과 분석
with open("results.json", "r") as f:
    data = json.load(f)

# 모든 청크 응답 결합
full_response = "\n\n".join([
    result['response']
    for result in data['results']
])

# 통계
print(f"총 비용: ${data['total_cost']:.2f}")
print(f"평균 청크당 비용: ${data['total_cost'] / len(data['results']):.4f}")
```

## 📁 프로젝트 구조

```
largeFileFeedback/
├── app.py                     # Flask 웹 서버
├── templates/
│   └── index.html            # 웹 인터페이스 UI
├── static/
│   ├── css/                  # CSS 파일
│   └── js/                   # JavaScript 파일
├── document_preprocessor.py    # 문서 전처리 (텍스트/이미지 추출)
├── llm_large_file_processor.py # 청킹 및 상태 관리
├── integrated_processor.py     # 통합 파이프라인
├── cli_processor.py           # CLI 인터페이스
├── demo.py                    # 데모 및 예제
├── requirements.txt           # 패키지 의존성
├── README.md                  # 이 파일
├── uploads/                   # 업로드된 파일 (자동 생성)
├── results/                   # 처리 결과 (자동 생성)
├── processing_states/         # 처리 상태 저장 (자동 생성)
└── chunks/                    # 청크 캐시 (자동 생성)
```

## 🐛 문제 해결

### 문제: 메모리 부족

```python
# 해결: 더 작은 청크 사용
chunks = processor.preprocess_and_chunk(
    file_path="huge_file.pdf",
    chunk_size=50000  # 기본값의 절반
)
```

### 문제: API 속도 제한

```python
import time

# 해결: 청크 사이에 지연 추가
class RateLimitedProcessor(IntegratedProcessor):
    def _call_llm_api(self, *args, **kwargs):
        result = super()._call_llm_api(*args, **kwargs)
        time.sleep(1)  # 1초 대기
        return result
```

### 문제: 특정 청크에서 오류

처리 중 오류가 발생하면 진행 상황이 자동으로 저장됩니다. `resume` 명령으로 재개하세요:

```bash
python cli_processor.py resume document.pdf
```

## ⚡ 성능 팁

1. **청크 사이즈 최적화**: 큰 청크는 API 호출 수를 줄이지만 메모리를 더 사용합니다.
2. **자동 저장**: 10청크마다 자동으로 상태가 저장됩니다.
3. **캐싱**: 동일한 파일의 청크는 재사용됩니다.
4. **이미지 최적화**: 이미지 크기를 조정하여 토큰 비용을 절감합니다.

## 📄 라이센스

이 프로젝트는 MIT 라이센스 하에 배포됩니다. 교육 및 상업적 목적으로 자유롭게 사용할 수 있습니다.

## 🤝 기여

버그 리포트, 기능 요청, 풀 리퀘스트를 환영합니다!

## 📞 지원

문제가 발생하면:
1. `python cli_processor.py status` 명령으로 현재 상태 확인
2. 처리 상황은 자동으로 저장됨
3. 언제든지 재개 가능
4. 데모 모드(`python demo.py`)로 시스템 테스트

---

**Happy Processing! 🚀**
