from .main import main
from dotenv import load_dotenv

load_dotenv()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAborted by user.")
