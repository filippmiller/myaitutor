
import os

def fix_env():
    try:
        with open(".env", "rb") as f:
            content = f.read()
        
        # Replace null bytes with nothing or newlines if appropriate, but usually nulls shouldn't be there.
        # Also check for other weird chars.
        # It seems 'echo' in PowerShell might have outputted UTF-16 LE which has nulls between chars.
        
        print(f"Original length: {len(content)}")
        
        # Try decoding as utf-16 if it looks like it
        if content.startswith(b'\xff\xfe') or b'\x00' in content:
            try:
                # If it's mixed, this is hard. Let's try to decode as utf-16
                text = content.decode('utf-16')
                print("Detected UTF-16")
            except:
                # Fallback: remove nulls
                text = content.replace(b'\x00', b'').decode('utf-8', errors='ignore')
                print("Removed nulls")
        else:
            text = content.decode('utf-8')
            
        # Clean up lines
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        
        with open(".env", "w", encoding="utf-8") as f:
            for line in lines:
                f.write(line + "\n")
                
        print("Fixed .env")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    fix_env()
