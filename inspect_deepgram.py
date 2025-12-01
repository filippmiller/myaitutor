
import deepgram
import inspect
import pkgutil

print(f"Deepgram version: {getattr(deepgram, '__version__', 'unknown')}")
print(f"Deepgram path: {deepgram.__path__}")

print("\nTop level attributes:")
for name in dir(deepgram):
    if not name.startswith("_"):
        print(f" - {name}")

print("\nWalking packages:")
for importer, modname, ispkg in pkgutil.walk_packages(deepgram.__path__, deepgram.__name__ + "."):
    print(f"Found module: {modname}")
