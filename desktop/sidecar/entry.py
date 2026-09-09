"""PyInstaller entry: the frozen executable starts here."""
import multiprocessing

if __name__ == "__main__":
    multiprocessing.freeze_support()
    from rapport.sidecar import main

    main()
