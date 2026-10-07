"""`python -m videorescue` → interfaz web local (navegador). Con `--desktop`, ventana nativa."""
import sys

def main():
    if "--desktop" in sys.argv:
        from .desktop import main as run
    else:
        from .app import main as run
    run()

if __name__ == "__main__":
    main()
