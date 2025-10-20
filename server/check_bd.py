from app.models.BDLibrary import BDLibrary
import asyncio

async def check():
    bds = await BDLibrary.all()
    print(f'Total BDs: {len(bds)}')
    for bd in bds[:5]:
        print(f'BD {bd.id}: {bd.title} - duration: {bd.duration}')

asyncio.run(check())

