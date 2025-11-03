# create_approval_table.py
from backend.app import create_app
from backend.database import db
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base

app = create_app()
Base = declarative_base()

class ApprovalNotification(Base):
    __tablename__ = "approval_notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    document_type = Column(String, nullable=False)
    document_id = Column(Integer, nullable=False)
    status = Column(String, nullable=False)
    message = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_read = Column(Boolean, default=False)


with app.app_context():
    # Bind metadata to your db engine
    Base.metadata.create_all(bind=db.engine)
    print("✅ Approval notifications table created successfully!")
