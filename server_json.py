import asyncio
import os

from io import BytesIO
from fastapi import FastAPI
from pydantic import BaseModel
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import  select, func, Table, MetaData, Column, Integer, String, Float, BigInteger
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import JSONB
from fastapi.responses import StreamingResponse

DATABASE_URL = os.getenv("DATABASE_URL", 'postgresql+asyncpg://user:password@db/database_name')

app = FastAPI()

engine = create_async_engine(DATABASE_URL, echo=True)
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

metadata = MetaData()
data_table = Table('data', metadata,
    Column('id', Integer, primary_key=True),
    Column('data', JSONB)
)

@app.on_event("startup")
async def startup():
    while True:
        try:
            async with engine.begin() as conn:
                await conn.run_sync(metadata.create_all)
            break  # If connection is successful, break the loop
        except Exception as e:  # Catch exceptions related to the DB connection
            print(f"Database connection failed with error: {e}")
            print("Retrying in 3 seconds...")
            await asyncio.sleep(3)  # Wait for 3 seconds before retrying

class Item(BaseModel):
        time: int
        node: int
        combined_power: float
        cpu_energy: float
        gpu_energy: float
        ane_energy: float
        time_delta: int
        screen_energy: float
        project: str
        type: str

@app.post("/save")
async def create_item(item: Item):
    async with async_session() as session:
        stmt = insert(data_table).values(data=item.dict())
        await session.execute(stmt)
        await session.commit()

@app.get("/last_time/{node_id}")
async def get_max_time(node_id: int):
    async with async_session() as session:
        stmt = select(func.max(data_table.c.data['time'].cast(BigInteger))).where(data_table.c.data['node'].cast(Integer) == node_id)
        result = await session.execute(stmt)
        max_time = result.scalar()
        if max_time is None:
            return {"error": "No data found for this node."}
        else:
            return {"last_time": max_time}

@app.get("/badge/{project}")
async def get_project_badge(project: str):
    async with async_session() as session:
        stmt = select(
            func.sum(data_table.c.data['cpu_energy'].cast(Float)),
            func.sum(data_table.c.data['gpu_energy'].cast(Float)),
            func.sum(data_table.c.data['ane_energy'].cast(Float))
        ).where(data_table.c.data['project'].astext == project)
        result = await session.execute(stmt)
        cpu_energy, gpu_energy, ane_energy = result.one()

    total_energy = cpu_energy + gpu_energy + ane_energy

    # Create image
    img = Image.new('RGB', (200, 30), color = (73, 109, 137))
    d = ImageDraw.Draw(img)
    d.text((10,10), f"Total Energy: {total_energy} mJ", fill=(255, 255, 0))

    # Save to a BytesIO stream and serve
    img_io = BytesIO()
    img.save(img_io, 'JPEG', quality=70)
    img_io.seek(0)
    return StreamingResponse(img_io, media_type="image/jpeg")


@app.get("/")
async def read_root():
    return {"message": "Welcome to the index page!"}
