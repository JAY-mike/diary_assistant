from datetime import datetime
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Depends
from sqlmodel import Field, SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from contextlib import asynccontextmanager
import json
import redis.asyncio as redis # ⚠️ 核心：必须引入 asyncio 版本
from fastapi.encoders import jsonable_encoder


# #==================
# # 1.定义数据模型
# #==================
# class Diary(SQLModel,table=True):
#     __tablename__= "diaries"  #显式设置表名，与之前的SQL对应
#     __table_args__ = {"extend_existing": True}  #允许扩展现有表，避免重复定义错误

#     #Field函数用于定义字段属性，default=None表示默认值为None，primary_key=True表示这是主键
#     id: Optional[int] = Field(default=None,primary_key=True)
#     title: str
#     content: str
#     mood: Optional[str] = None
#     #default_factory 确保每次生成对象时，都获取当前的时间，而不是在定义类时就固定一个时间
#     created_at: Optional[datetime] = Field(default_factory=datetime.now)

# 建立全局异步 Redis 客户端
# decode_responses=True 确保我们从 Redis 取出的是直观的字符串，而不是 bytes 字节码
redis_client = redis.Redis(host='127.0.0.1', port=6379, decode_responses=True)






class DiaryBase(SQLModel):
    """日记基础数据模型，包含公共字段"""
    title: str
    content: str
    mood: Optional[str] = None
    
class DiaryCreate(DiaryBase):
    """创建专门用于post请求的数据模型"""
    pass

class Diary(DiaryBase,table=True):
    """日记数据模型，用于表示数据库中的日记记录"""
    __tablename__= "diaries"  #显式设置表名，与之前的SQL对应
    __table_args__ = {"extend_existing": True}  #允许扩展现有表，避免重复定义错误

    id: Optional[int] = Field(default=None,primary_key=True)
    created_at: Optional[datetime] = Field(default_factory=datetime.now)

class DiaryRead(DiaryBase):
    """读取专门用于get请求的数据模型,包含id和created_at字段"""
    id: int
    created_at: datetime

#==================
# 2.创建数据库引擎和表
#==================

ASYNC_DATABASE_URL = "mysql+aiomysql://root:123456@127.0.0.1:3306/diary_db"

#创建数据库引擎，echo=True表示输出SQL日志，方便调试
engine = create_async_engine(ASYNC_DATABASE_URL, echo=True)

#创建会话工厂，每次需要数据库会话时调用它
AsyncSessionLocal = async_sessionmaker(
    autocommit=False, 
    autoflush=False,
    bind=engine, 
    class_=AsyncSession,
    expire_on_commit=False)  #防止提交后对象过期，保持数据可用

#依赖注入函数，每一次请求都会创建一个新的数据库会话，并在请求结束后关闭它
    # def get_session():
        
    #     with Session(engine) as session:
    #         yield session


# async def get_session():
#     session = AsyncSessionLocal()  #创建一个新的数据库会话
#     try:
#         yield session  #将会话对象提供给请求处理函数使用
#     finally:
#         await session.close()  #确保请求结束后关闭会话，释放数据库连接

async def get_session():
    # async with 会自动处理开启和关闭，哪怕中途报错了也会安全释放连接
    async with AsyncSessionLocal() as session:
        yield session


#======================
#新增应用的生命周期事件，确保在应用启动时创建数据库表
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("应用启动中，正在创建数据库表...")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)  #异步创建表
    print("数据库表创建完成，应用已启动！")

    yield  #这里是应用运行的主体，所有请求处理都在这个yield之后执行

    print("应用正在关闭，正在清理资源...")













#==================
# 3.创建FastAPI应用和路由
#==================

app = FastAPI(
    title='解压日记API-异步版本',
    description='我的第一个异步全栈AI应用后端支撑',
    lifespan=lifespan  #注册生命周期事件
)

#==================
#4. 核心CRUD接口路由
#==================

@app.post("/diaries/",response_model = DiaryRead)
async def create_diary(diary: DiaryCreate,session: AsyncSession = Depends(get_session)):
    """
    写一篇新日记
    # """
    diary = Diary.model_validate(diary)  #将输入的DiaryCreate对象转换为Diary对象，准备保存到数据库
    session.add(diary)      #添加到会话
    await session.commit()        #提交到数据库保存
    await session.refresh(diary)  #刷新对象以获取数据库生成的ID和时间等信息
    return diary

    # # 1. 先把前端传入的 DTO 对象转换为纯纯的 Python 字典
    # # 注意：如果你使用的是较老的 Pydantic V1，这行需要写成 diary.dict()
    # diary_data = diary.model_dump() 

    # # 2. 使用字典解包语法 (**)，将其喂给数据库模型，重新实例化一个标准对象
    # db_diary = Diary(**diary_data)

    # # 3. 接下来把带有追踪芯片的 db_diary 交给数据库会话即可
    # session.add(db_diary)      
    # session.commit()        
    # session.refresh(db_diary)  

    # return db_diary

@app.get("/diaries/",response_model=List[DiaryRead])
async def read_diaries(skip: int = 0, limit: int = 10, session: AsyncSession = Depends(get_session)):
    """
    获取日记列表(支持offset/limit分页)
    """
    statement = select(Diary).offset(skip).limit(limit)  #构建查询语句，支持分页
    diaries = await session.exec(statement).all()  #执行查询并获取结果
    return diaries

@app.get("/diaries/{diary_id}",response_model=DiaryRead)
async def read_diary(diary_id: int, session: AsyncSession = Depends(get_session)):
    """
    获取指定ID的日记
    """
    diary = await session.get(Diary, diary_id)  #根据ID获取日记
    if not diary:
        raise HTTPException(status_code=404, detail="Diary not found")  #如果没有找到，抛出404错误
    return diary

@app.delete("/diaries/{diary_id}")
async def delete_diary(diary_id: int, session: AsyncSession = Depends(get_session)):
    """
    删除指定ID的日记
    """
    diary = await session.get(Diary, diary_id)  #根据ID获取日记
    if not diary:
        raise HTTPException(status_code=404, detail="Diary not found")  #如果没有找到，抛出404错误
    
    await session.delete(diary)
    await session.commit()        #提交删除操作
    return {"message": "Diary deleted successfully"}  #返回删除成功的消息

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main1:app", host="127.0.0.1", port=8002, reload=True)  #启动FastAPI应用，reload=True表示代码修改后自动重启服务器