from fastapi import FastAPI, HTTPException, Depends, status, Form
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import create_engine, Column, Integer, String, MetaData, Table
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from pymongo import MongoClient
# from fastapi import FastAPI, HTTPException, Depends, status
# from fastapi.security import OAuth2PasswordBearer
# from datetime import datetime, timedelta
# from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from fastapi import Request

# FastAPI setup
app = FastAPI()
templates = Jinja2Templates(directory="templates")

# OAuth2 for authentication
SECRET_KEY = "your-secret-key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Password hashing
password_hashing = CryptContext(schemes=["bcrypt"], deprecated="auto")

# SQL database setup
DATABASE_URL = "sqlite:///./sql_app.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# MongoDB setup
mongo_client = MongoClient("mongodb://localhost:27017/")
mongo_db = mongo_client["product_catalog"]

# SQL User Table
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)

# MongoDB Product Collection
products_collection = mongo_db["products"]

# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Dependency to verify token and get current user
def get_current_user(token: str = Depends("oauth2_scheme")):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        return username
    except JWTError:
        raise credentials_exception

# Generate access token
def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Models
class Product(BaseModel):
    name: str
    description: str

class UserCreate(BaseModel):
    username: str
    password: str

class UserLogin(UserCreate):
    pass

# HTML templates
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# API Endpoints
@app.post("/register")
def register(user: UserCreate, db: Session = Depends(get_db)):
    hashed_password = password_hashing.hash(user.password)
    db_user = User(username=user.username, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return {"username": db_user.username}

@app.post("/token")
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/products")
def list_products(db: Session = Depends(get_db)):
    # Implementation to list products from MongoDB
    products = products_collection.find()
    return [{"name": product["name"], "description": product["description"]} for product in products]

@app.post("/add-product")
def add_product(product: Product, db: Session = Depends(get_db)):
    # Implementation to add a new product to MongoDB
    products_collection.insert_one({"name": product.name, "description": product.description})
    return {"message": "Product added successfully"}

@app.get("/product/{product_id}")
def get_product(product_id: int, db: Session = Depends(get_db)):
    # Implementation to get product details from MongoDB
    product = products_collection.find_one({"_id": product_id})
    if product:
        return {"name": product["name"], "description": product["description"]}
    else:
        raise HTTPException(status_code=404, detail="Product not found")
