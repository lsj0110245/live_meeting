import os
from faster_whisper import WhisperModel

def download_model():
    model_size = "deepdml/faster-whisper-large-v3-turbo-ct2"
    print(f"Downloading {model_size} model during build...")
    # 먼저 환경 변수에서 확인
    hf_token = os.environ.get("HUGGING_FACE_TOKEN")
    
    # 환경 변수가 없으면 Docker Secret 파일에서 확인
    secret_path = "/run/secrets/hugging_face_token"
    if not hf_token and os.path.exists(secret_path):
        with open(secret_path, "r", encoding="utf-8") as f:
            hf_token = f.read().strip()
            
    if hf_token:
        os.environ["HF_TOKEN"] = hf_token
        print("Using Hugging Face Token for download.")
    else:
        print("No Hugging Face Token provided. Download might fail if model is private/gated.")
        
    try:
        # GPU 없이 CPU 모드, 메모리 최적화를 위해 int8로 다운로드 (캐싱 목적이므로 모델 가중치만 받아옵니다)
        WhisperModel(model_size, device="cpu", compute_type="int8")
        print("Model successfully downloaded and cached!")
    except Exception as e:
        print(f"Error downloading model: {e}")
        raise e

if __name__ == "__main__":
    download_model()
