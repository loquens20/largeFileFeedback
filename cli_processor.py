#!/usr/bin/env python3
"""
대용량 파일 LLM 처리 CLI 도구

사용법:
    python cli_processor.py process document.pdf --prompt "요약해주세요"
    python cli_processor.py resume document.pdf
    python cli_processor.py status
    python cli_processor.py export results.json
"""

import argparse
import sys
import signal
from pathlib import Path

from integrated_processor import IntegratedProcessor


class CLIProcessor:
    """CLI 인터페이스"""

    def __init__(self):
        self.processor = IntegratedProcessor()

        # Ctrl+C 핸들러 등록
        signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Ctrl+C 처리"""
        print("\n\n⚠️  중단 신호 감지 (Ctrl+C)")
        print("진행 중인 청크 처리를 완료한 후 일시정지합니다...")
        self.processor.request_pause()

    def process(self, args):
        """파일 처리 시작"""
        # API 클라이언트 설정
        api_client = self._setup_api_client(args.api, args.api_key)
        self.processor.api_client = api_client

        # 시스템 프롬프트
        system_prompt = args.system_prompt or "당신은 문서 분석 전문가입니다."

        # 사용자 프롬프트 템플릿
        user_prompt = args.prompt or "다음 내용을 분석해주세요:\n\n{chunk_text}"

        # 처리 실행
        state = self.processor.process_file(
            file_path=args.file,
            system_prompt=system_prompt,
            user_prompt_template=user_prompt,
            model=args.model,
            output_tokens=args.max_output,
            auto_confirm=args.yes
        )

        # 결과 출력
        if args.output:
            self.processor.export_results(state, args.output)

    def resume(self, args):
        """중단된 처리 재개"""
        # 상태 확인
        state = self.processor.file_processor.load_state(args.file)

        if state is None:
            print(f"❌ '{args.file}'에 대한 저장된 상태를 찾을 수 없습니다.")
            print("   처음부터 시작하려면 'process' 명령을 사용하세요.")
            return

        print(f"\n📂 저장된 상태 로드")
        print(f"   파일: {state.file_path}")
        print(f"   진행: {state.processed_chunks}/{state.total_chunks} 청크")
        print(f"   모델: {state.current_model}")
        print(f"   누적 비용: ${state.total_cost:.4f}")

        # 모델 변경 옵션
        if args.model and args.model != state.current_model:
            print(f"\n🔄 모델 변경: {state.current_model} → {args.model}")
            self.processor.file_processor.change_model(args.model)

        # API 클라이언트 설정
        api_client = self._setup_api_client(args.api, args.api_key)
        self.processor.api_client = api_client

        # 청크 로드
        chunks = self.processor.preprocess_and_chunk(args.file)

        # 처리 재개
        print("\n▶️  처리 재개...")
        self.processor._process_chunks(
            chunks=chunks,
            state=state,
            system_prompt=args.system_prompt or "당신은 문서 분석 전문가입니다.",
            user_prompt_template=args.prompt or "다음 내용을 분석해주세요:\n\n{chunk_text}",
            model=state.current_model,
            output_tokens=args.max_output
        )

        # 결과 출력
        if args.output:
            self.processor.export_results(state, args.output)

    def status(self, args):
        """처리 상태 확인"""
        state_files = list(self.processor.file_processor.state_dir.glob("*.json"))

        if not state_files:
            print("저장된 처리 상태가 없습니다.")
            return

        print(f"\n{'='*70}")
        print(f"저장된 처리 상태: {len(state_files)}개")
        print(f"{'='*70}\n")

        for state_file in state_files:
            with open(state_file, 'r') as f:
                import json
                state_data = json.load(f)

            progress = (state_data['processed_chunks'] / state_data['total_chunks'] * 100)

            print(f"📄 {Path(state_data['file_path']).name}")
            print(f"   진행: {state_data['processed_chunks']}/{state_data['total_chunks']} ({progress:.1f}%)")
            print(f"   모델: {state_data['current_model']}")
            print(f"   비용: ${state_data['total_cost']:.4f}")
            print(f"   업데이트: {state_data['updated_at'][:19]}")
            print()

    def export(self, args):
        """결과 내보내기"""
        if not args.file:
            print("❌ 파일 경로를 지정해주세요.")
            return

        state = self.processor.file_processor.load_state(args.file)
        if state is None:
            print(f"❌ '{args.file}'에 대한 저장된 상태를 찾을 수 없습니다.")
            return

        output_path = args.output or f"results_{Path(args.file).stem}.json"
        self.processor.export_results(state, output_path)

    def _setup_api_client(self, api_type: str, api_key: str = None):
        """API 클라이언트 설정"""
        if api_type == 'anthropic':
            try:
                from anthropic import Anthropic

                if api_key is None:
                    import os
                    api_key = os.getenv('ANTHROPIC_API_KEY')

                if not api_key:
                    print("⚠️  ANTHROPIC_API_KEY가 설정되지 않았습니다.")
                    print("   데모 모드로 실행됩니다.")
                    return None

                return Anthropic(api_key=api_key)

            except ImportError:
                print("❌ anthropic 패키지가 설치되지 않았습니다.")
                print("   pip install anthropic")
                sys.exit(1)

        elif api_type == 'openai':
            try:
                from openai import OpenAI

                if api_key is None:
                    import os
                    api_key = os.getenv('OPENAI_API_KEY')

                if not api_key:
                    print("⚠️  OPENAI_API_KEY가 설정되지 않았습니다.")
                    print("   데모 모드로 실행됩니다.")
                    return None

                return OpenAI(api_key=api_key)

            except ImportError:
                print("❌ openai 패키지가 설치되지 않았습니다.")
                print("   pip install openai")
                sys.exit(1)

        else:
            print(f"⚠️  알 수 없는 API 타입: {api_type}")
            print("   데모 모드로 실행됩니다.")
            return None


def main():
    parser = argparse.ArgumentParser(
        description='대용량 파일 LLM 처리 도구',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예제:
  # 새 파일 처리
  %(prog)s process document.pdf --prompt "요약해주세요" --model claude-haiku-4

  # 중단된 처리 재개
  %(prog)s resume document.pdf

  # 다른 모델로 변경하여 재개
  %(prog)s resume document.pdf --model gpt-4o-mini

  # 처리 상태 확인
  %(prog)s status

  # 결과 내보내기
  %(prog)s export document.pdf --output results.json
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='명령')

    # process 명령
    process_parser = subparsers.add_parser('process', help='새 파일 처리')
    process_parser.add_argument('file', help='처리할 파일')
    process_parser.add_argument('--prompt', '-p', help='LLM 프롬프트')
    process_parser.add_argument('--system-prompt', help='시스템 프롬프트')
    process_parser.add_argument('--model', '-m', default='claude-haiku-4',
                               help='사용할 모델 (기본: claude-haiku-4)')
    process_parser.add_argument('--max-output', type=int, default=1000,
                               help='최대 출력 토큰 (기본: 1000)')
    process_parser.add_argument('--api', choices=['anthropic', 'openai'],
                               default='anthropic', help='API 제공자')
    process_parser.add_argument('--api-key', help='API 키')
    process_parser.add_argument('--output', '-o', help='결과 저장 경로')
    process_parser.add_argument('--yes', '-y', action='store_true',
                               help='비용 확인 없이 바로 실행')

    # resume 명령
    resume_parser = subparsers.add_parser('resume', help='중단된 처리 재개')
    resume_parser.add_argument('file', help='재개할 파일')
    resume_parser.add_argument('--model', '-m', help='모델 변경')
    resume_parser.add_argument('--prompt', '-p', help='LLM 프롬프트')
    resume_parser.add_argument('--system-prompt', help='시스템 프롬프트')
    resume_parser.add_argument('--max-output', type=int, default=1000,
                               help='최대 출력 토큰')
    resume_parser.add_argument('--api', choices=['anthropic', 'openai'],
                               default='anthropic', help='API 제공자')
    resume_parser.add_argument('--api-key', help='API 키')
    resume_parser.add_argument('--output', '-o', help='결과 저장 경로')

    # status 명령
    status_parser = subparsers.add_parser('status', help='처리 상태 확인')

    # export 명령
    export_parser = subparsers.add_parser('export', help='결과 내보내기')
    export_parser.add_argument('file', nargs='?', help='파일')
    export_parser.add_argument('--output', '-o', help='출력 경로')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    cli = CLIProcessor()

    if args.command == 'process':
        cli.process(args)
    elif args.command == 'resume':
        cli.resume(args)
    elif args.command == 'status':
        cli.status(args)
    elif args.command == 'export':
        cli.export(args)


if __name__ == '__main__':
    main()
