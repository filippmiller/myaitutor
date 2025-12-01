
import deepgram
import pkgutil
import inspect

target = "LiveOptions"
found = False

def search_module(module, path_prefix):
    global found
    if found: return

    try:
        if hasattr(module, target):
            print(f"FOUND {target} in {module.__name__}")
            found = True
            return
    except:
        pass

    if hasattr(module, "__path__"):
        for importer, modname, ispkg in pkgutil.iter_modules(module.__path__):
            if found: return
            full_name = f"{module.__name__}.{modname}"
            try:
                submod = __import__(full_name, fromlist=[""])
                # The import might return the top package, so we need to traverse
                components = full_name.split('.')
                curr = submod
                # This traversal is tricky with __import__, let's just use sys.modules or similar if needed
                # But actually __import__ with fromlist returns the module.
                
                search_module(submod, full_name)
            except Exception as e:
                # print(f"Could not import {full_name}: {e}")
                pass

search_module(deepgram, "deepgram")
if not found:
    print(f"{target} not found")
