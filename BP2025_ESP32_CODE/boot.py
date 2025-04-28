import main

try:
    main.main()
except OSError as e:
    print(f"Couldn't start unit: {e}")
