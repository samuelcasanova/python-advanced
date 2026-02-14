from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional

app = FastAPI(title="To-Do List API")

class TodoItem(BaseModel):
    id: Optional[int] = None
    title: str
    description: Optional[str] = None
    completed: bool = False

# In-memory storage for demonstration (can be upgraded to SQLite later)
todos = []
id_counter = 1

@app.get("/todos", response_model=List[TodoItem])
async def get_todos():
    return todos

@app.post("/todos", response_model=TodoItem, status_code=201)
async def create_todo(todo: TodoItem):
    global id_counter
    todo.id = id_counter
    todos.append(todo)
    id_counter += 1
    return todo

@app.get("/todos/{todo_id}", response_model=TodoItem)
async def get_todo(todo_id: int):
    for item in todos:
        if item.id == todo_id:
            return item
    raise HTTPException(status_code=404, detail="Todo item not found")

@app.put("/todos/{todo_id}", response_model=TodoItem)
async def update_todo(todo_id: int, updated_todo: TodoItem):
    for index, item in enumerate(todos):
        if item.id == todo_id:
            updated_todo.id = todo_id
            todos[index] = updated_todo
            return updated_todo
    raise HTTPException(status_code=404, detail="Todo item not found")

@app.delete("/todos/{todo_id}", status_code=204)
async def delete_todo(todo_id: int):
    for index, item in enumerate(todos):
        if item.id == todo_id:
            todos.pop(index)
            return
    raise HTTPException(status_code=404, detail="Todo item not found")

@app.get("/health")
async def health_check():
    return {"status": "ok"}
