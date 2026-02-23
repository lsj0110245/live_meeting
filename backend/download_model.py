import os
from faster_whisper import WhisperModel

def download_model():
    model_size = "deepdml/faster-whisper-large-v3-turbo-ct2"
    print(f"Downloading {model_size} model during build...")
    hf_token = os.environ.get("HUGGING_FACE_TOKEN")
    if hf_token:
        os.environ["HF_TOKEN"] = hf_token
        print("Using HUGGING_FACE_TOKEN for download.")
    else:
        print("No HUGGING_FACE_TOKEN provided. Download might fail if model is private/gated, or be rate-limited.")
        
    try:
        # GPU 없이 CPU 모드, 메모리 최적화를 위해 int8로 다운로드 (캐싱 목적이므로 모델 가중치만 받아옵니다)
        WhisperModel(model_size, device="cpu", compute_type="int8")
        print("Model successfully downloaded and cached!")
    except Exception as e:
        print(f"Error downloading model: {e}")
        raise e

if __name__ == "__main__":
    download_model()
