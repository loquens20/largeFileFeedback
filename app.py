import os
import json
import uuid
import threading
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename
from integrated_processor import IntegratedProcessor
from llm_large_file_processor import LargeFileProcessor

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['RESULTS_FOLDER'] = 'results'
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max file size

# Ensure folders exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['RESULTS_FOLDER'], exist_ok=True)

# Store job status in memory (for production, use Redis or database)
jobs = {}
job_locks = {}

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'docx', 'pptx', 'xlsx'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_file_async(job_id, file_path, prompt, model, api_key, chunk_size, chunk_overlap, optimize_images):
    """Process file in background thread"""
    try:
        # Update job status
        jobs[job_id]['status'] = 'preprocessing'
        jobs[job_id]['message'] = '파일 전처리 중...'

        # Initialize processor
        processor = IntegratedProcessor()

        # Preprocess and chunk
        jobs[job_id]['message'] = '청크 생성 중...'
        chunks = processor.preprocess_and_chunk(
            file_path,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            optimize_images=optimize_images
        )

        jobs[job_id]['total_chunks'] = len(chunks)
        jobs[job_id]['message'] = f'총 {len(chunks)}개 청크 생성 완료'

        # Estimate cost
        jobs[job_id]['status'] = 'estimating'
        jobs[job_id]['message'] = '비용 추정 중...'

        llm_processor = LargeFileProcessor()
        cost_info = llm_processor.estimate_remaining_cost(chunks, 0, model)
        jobs[job_id]['estimated_cost'] = cost_info

        # Process chunks
        jobs[job_id]['status'] = 'processing'
        jobs[job_id]['processed_chunks'] = 0

        # Set API key based on model
        if model.startswith('claude'):
            os.environ['ANTHROPIC_API_KEY'] = api_key
        else:
            os.environ['OPENAI_API_KEY'] = api_key

        results = []
        for i, chunk in enumerate(chunks):
            if jobs[job_id]['status'] == 'cancelled':
                jobs[job_id]['message'] = '처리가 취소되었습니다'
                return

            jobs[job_id]['message'] = f'청크 {i+1}/{len(chunks)} 처리 중...'

            # Process chunk
            result = processor._process_single_chunk(
                chunk,
                prompt,
                model,
                i
            )

            results.append(result)
            jobs[job_id]['processed_chunks'] = i + 1
            jobs[job_id]['progress'] = int((i + 1) / len(chunks) * 100)

        # Save results
        result_file = os.path.join(
            app.config['RESULTS_FOLDER'],
            f'{job_id}_result.json'
        )

        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump({
                'job_id': job_id,
                'file_name': jobs[job_id]['file_name'],
                'model': model,
                'prompt': prompt,
                'total_chunks': len(chunks),
                'estimated_cost': cost_info,
                'results': results,
                'completed_at': datetime.now().isoformat()
            }, f, ensure_ascii=False, indent=2)

        jobs[job_id]['status'] = 'completed'
        jobs[job_id]['message'] = '처리 완료!'
        jobs[job_id]['result_file'] = result_file

    except Exception as e:
        jobs[job_id]['status'] = 'failed'
        jobs[job_id]['message'] = f'오류 발생: {str(e)}'
        jobs[job_id]['error'] = str(e)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    # Validate file
    if 'file' not in request.files:
        return jsonify({'error': '파일이 없습니다'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '파일이 선택되지 않았습니다'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': f'지원하지 않는 파일 형식입니다. 허용: {", ".join(ALLOWED_EXTENSIONS)}'}), 400

    # Get parameters
    prompt = request.form.get('prompt', '이 문서를 요약해주세요')
    model = request.form.get('model', 'claude-haiku-4')
    api_key = request.form.get('api_key', '')
    chunk_size = int(request.form.get('chunk_size', 80000))
    chunk_overlap = int(request.form.get('chunk_overlap', 4000))
    optimize_images = request.form.get('optimize_images', 'true') == 'true'

    if not api_key:
        return jsonify({'error': 'API 키가 필요합니다'}), 400

    # Save file
    filename = secure_filename(file.filename)
    job_id = str(uuid.uuid4())
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], f'{job_id}_{filename}')
    file.save(file_path)

    # Create job
    jobs[job_id] = {
        'job_id': job_id,
        'file_name': filename,
        'file_path': file_path,
        'status': 'queued',
        'message': '대기 중...',
        'progress': 0,
        'created_at': datetime.now().isoformat(),
        'model': model,
        'prompt': prompt
    }
    job_locks[job_id] = threading.Lock()

    # Start processing in background
    thread = threading.Thread(
        target=process_file_async,
        args=(job_id, file_path, prompt, model, api_key, chunk_size, chunk_overlap, optimize_images)
    )
    thread.daemon = True
    thread.start()

    return jsonify({
        'job_id': job_id,
        'message': '파일 업로드 성공. 처리를 시작합니다.'
    })

@app.route('/status/<job_id>', methods=['GET'])
def get_status(job_id):
    if job_id not in jobs:
        return jsonify({'error': '작업을 찾을 수 없습니다'}), 404

    job = jobs[job_id]
    return jsonify({
        'job_id': job_id,
        'file_name': job['file_name'],
        'status': job['status'],
        'message': job['message'],
        'progress': job.get('progress', 0),
        'total_chunks': job.get('total_chunks', 0),
        'processed_chunks': job.get('processed_chunks', 0),
        'estimated_cost': job.get('estimated_cost'),
        'model': job.get('model'),
        'created_at': job['created_at']
    })

@app.route('/download/<job_id>', methods=['GET'])
def download_result(job_id):
    if job_id not in jobs:
        return jsonify({'error': '작업을 찾을 수 없습니다'}), 404

    job = jobs[job_id]
    if job['status'] != 'completed':
        return jsonify({'error': '처리가 완료되지 않았습니다'}), 400

    if 'result_file' not in job:
        return jsonify({'error': '결과 파일을 찾을 수 없습니다'}), 404

    return send_file(
        job['result_file'],
        as_attachment=True,
        download_name=f"{job['file_name']}_result.json"
    )

@app.route('/cancel/<job_id>', methods=['POST'])
def cancel_job(job_id):
    if job_id not in jobs:
        return jsonify({'error': '작업을 찾을 수 없습니다'}), 404

    jobs[job_id]['status'] = 'cancelled'
    return jsonify({'message': '작업이 취소되었습니다'})

@app.route('/jobs', methods=['GET'])
def list_jobs():
    return jsonify([{
        'job_id': job_id,
        'file_name': job['file_name'],
        'status': job['status'],
        'progress': job.get('progress', 0),
        'created_at': job['created_at']
    } for job_id, job in jobs.items()])

if __name__ == '__main__':
    print("=" * 60)
    print("LLM 대용량 파일 처리 웹 인터페이스")
    print("=" * 60)
    print("\n웹 서버 시작: http://localhost:5000")
    print("\n지원 파일 형식:", ", ".join(ALLOWED_EXTENSIONS))
    print("최대 파일 크기: 100MB")
    print("\nCtrl+C를 눌러 종료\n")
    app.run(debug=True, host='0.0.0.0', port=5000)
