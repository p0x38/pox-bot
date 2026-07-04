import edge_tts
import json

async def main():
    data = await edge_tts.list_voices()
    
    stringified = json.dumps(data, indent=4)
    print(stringified)
    
if __name__ == "__main__":
    import asyncio
    asyncio.run(main())