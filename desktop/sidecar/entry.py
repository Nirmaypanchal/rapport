"""PyInstaller entry: the frozen executable starts here."""
import multiprocessing

if __name__ == "__main__":
    multiprocessing.freeze_support()
    from dji_mic_app.sidecar import main

    main()
