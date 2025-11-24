from dotenv import load_dotenv
load_dotenv()

from .apis.cli import main
from .jarvis.jarvis_cli import interactive_loop

if __name__ == "__main__":
    try:
        # main()
        interactive_loop()
    except KeyboardInterrupt:
        print("\nAborted by user.")
