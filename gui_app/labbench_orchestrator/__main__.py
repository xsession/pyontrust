try:
    from .app import main
except ImportError:  # pragma: no cover
    from pyontrust_gui.app import main

if __name__ == "__main__":
    main()
