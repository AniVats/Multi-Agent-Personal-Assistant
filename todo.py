import os
import uuid
import sqlalchemy
from datetime import datetime
from typing import Optional, List

from sqlalchemy import (
    Column,
    String,
    DateTime,
    Enum,
    select,
    delete,
    update,
)
from sqlalchemy.orm import declarative_base, Session
from google.cloud.sql.connector import Connector
from google.adk.agents.llm_agent import Agent

# --- DATABASE LOGIC ---
Base = declarative_base()
connector = Connector()

def getconn():
    db_connection_name = os.environ.get("DB_CONNECTION_NAME")
    db_user = os.environ.get("DB_USER")
    db_password = os.environ.get("DB_PASSWORD")
    db_name = os.environ.get("DB_NAME", "tasks")

    return connector.connect(
        db_connection_name,
        "pg8000",
        user=db_user,
        password=db_password,
        db=db_name,
    )

engine = sqlalchemy.create_engine(
    "postgresql+pg8000://",
    creator=getconn,
)

class Todo(Base):
    __tablename__ = "todos"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(255), nullable=False)
    priority = Column(
        Enum("high", "medium", "low", name="priority_levels"), nullable=False, default="medium"
    )
    due_date = Column(DateTime, nullable=True)
    status = Column(Enum("pending", "done", name="status_levels"), default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)

def init_db():
    """Builds the table if it's missing."""
    Base.metadata.create_all(bind=engine)

def add_todo(
    title: str, priority: str = "medium", due_date: Optional[str] = None
) -> dict:
    """
    Adds a new task to the list.

    Args:
        title (str): The description of the task.
        priority (str): The urgency level. Must be one of: 'high', 'medium', 'low'.
        due_date (str, optional): The due date in ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS).

    Returns:
        dict: A dictionary containing the new task's ID and a status message.
    """
    init_db()
    with Session(engine) as session:
        due = datetime.fromisoformat(due_date) if due_date else None
        item = Todo(
            title=title,
            priority=priority.lower(),
            due_date=due,
        )
        session.add(item)
        session.commit()
        return {"id": item.id, "status": f"Task added ✅"}

def list_todos(status: str = "pending") -> list:
    """
    Lists tasks from the database, optionally filtering by status.

    Args:
        status (str, optional): The status to filter by. 'pending', 'done', or 'all'.
    """
    init_db()
    with Session(engine) as session:
        query = select(Todo)
        
        s_lower = status.lower()
        if s_lower != "all":
            query = query.where(Todo.status == s_lower)

        query = query.order_by(Todo.priority, Todo.created_at)

        results = session.execute(query).scalars().all()
        return [
            {
                "id": t.id,
                "task": t.title,
                "priority": t.priority,
                "status": t.status,
            }
            for t in results
        ]

def complete_todo(task_id: str) -> str:
    """Marks a specific task as 'done'."""
    init_db()
    with Session(engine) as session:
        session.execute(update(Todo).where(Todo.id == task_id).values(status="done"))
        session.commit()
        return f"Task {task_id} marked as done."

def delete_todo(task_id: str) -> str:
    """Permanently removes a task from the database."""
    init_db()
    with Session(engine) as session:
        session.execute(delete(Todo).where(Todo.id == task_id))
        session.commit()
        return f"Task {task_id} deleted."

# --- TODO SPECIALIST AGENT ---
todo_agent = Agent(
    model='gemini-2.5-flash',
    name='todo_specialist',
    description='A specialist agent that manages a structured SQL task list.',
    instruction='''
    You manage the user's task list using a PostgreSQL database.
    - Use add_todo when the user wants to remember something. If no priority is mentioned, mark it as 'medium'.
    - Use list_todos to show tasks.
    - Use complete_todo to mark a task as finished.
    - Use delete_todo to remove a task entirely.
    
    When marking a task as complete or deleting it, if the user doesn't provide the ID, 
    use list_todos first to find the correct ID for the task they described.
    ''',
    tools=[add_todo, list_todos, complete_todo, delete_todo],
)