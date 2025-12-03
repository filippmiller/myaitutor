import json
from typing import Optional
from datetime import datetime
from openai import OpenAI
from sqlmodel import Session, select
from app.models import (
    AppSettings, TutorRule, TutorRuleVersion, 
    AdminAIConversation, AdminAIMessage, UserAccount
)

SYSTEM_PROMPT = """You are an AI assistant for the AIlingva admin panel. Your role is to help the admin manage tutor behavior rules and query analytics.

**Capabilities:**
1. Create, update, or deactivate tutor behavior rules via tools
2. Query safe analytics (session counts, XP metrics, student activity)
3. Never execute arbitrary SQL - only use provided tools

**When the admin requests a rule change:**
- Parse the natural language request
- Determine scope (global/app/student/session)
- Determine type (greeting/toxicity_warning/difficulty_adjustment/other)
- Call the appropriate tool with structured data
- Confirm the action in your response

**Always respond with:**
- Human-readable summary of what you did
- Structured action plan (internally)

**Rule Types:**
- `greeting`: Rules for how the tutor starts sessions
- `toxicity_warning`: Rules for handling inappropriate language
- `difficulty_adjustment`: Rules for adapting lesson difficulty
- `language_mode`: Rules for language selection and mode-specific behavior (EN_ONLY/RU_ONLY/MIXED)
- `other`: Any other behavioral rules

**Scopes:**
- `global`: Applies to all students
- `student`: Applies to a specific student (requires student_id)
- `app`: Applies to a specific app version
- `session`: Applies to a specific session (future use)

Be helpful, clear, and always confirm actions taken.
"""

def get_or_create_conversation(session: Session, admin_user_id: int, conversation_id: Optional[int] = None) -> AdminAIConversation:
    """Get existing conversation or create a new one."""
    if conversation_id:
        conversation = session.get(AdminAIConversation, conversation_id)
        if not conversation or conversation.admin_user_id != admin_user_id:
            raise ValueError("Invalid conversation ID")
        return conversation
    
    # Create new conversation
    conversation = AdminAIConversation(
        admin_user_id=admin_user_id,
        status="open"
    )
    session.add(conversation)
    session.commit()
    session.refresh(conversation)
    return conversation

def save_message(session: Session, conversation_id: int, sender: str, content: str, message_type: str = "text") -> AdminAIMessage:
    """Save a message to the database."""
    message = AdminAIMessage(
        conversation_id=conversation_id,
        sender=sender,
        message_type=message_type,
        content=content
    )
    session.add(message)
    session.commit()
    session.refresh(message)
    return message

def list_rules_tool(session: Session, scope: Optional[str] = None, student_id: Optional[int] = None, is_active: Optional[bool] = None):
    """Tool: List tutor rules with optional filters."""
    statement = select(TutorRule)
    
    if scope:
        statement = statement.where(TutorRule.scope == scope)
    if student_id is not None:
        statement = statement.where(TutorRule.applies_to_student_id == student_id)
    if is_active is not None:
        statement = statement.where(TutorRule.is_active == is_active)
    
    rules = session.exec(statement.order_by(TutorRule.priority)).all()
    
    return {
        "rules": [
            {
                "id": rule.id,
                "scope": rule.scope,
                "type": rule.type,
                "title": rule.title,
                "description": rule.description,
                "priority": rule.priority,
                "is_active": rule.is_active,
                "source": rule.source
            }
            for rule in rules
        ]
    }

def create_rule_tool(
    session: Session,
    scope: str,
    type: str,
    title: str,
    description: str,
    trigger_condition: Optional[str] = None,
    action: Optional[str] = None,
    priority: int = 0
):
    """Tool: Create a new tutor rule."""
    # Create the rule
    rule = TutorRule(
        scope=scope,
        type=type,
        title=title,
        description=description,
        trigger_condition=trigger_condition,
        action=action,
        priority=priority,
        is_active=True,
        created_by="ai_admin",
        updated_by="ai_admin",
        source="ai_admin"
    )
    session.add(rule)
    session.commit()
    session.refresh(rule)
    
    # Create audit version
    version = TutorRuleVersion(
        rule_id=rule.id,
        scope=rule.scope,
        type=rule.type,
        title=rule.title,
        description=rule.description,
        trigger_condition=rule.trigger_condition,
        action=rule.action,
        priority=rule.priority,
        is_active=rule.is_active,
        changed_by="ai_admin",
        change_reason="Initial creation by AI Admin Assistant"
    )
    session.add(version)
    session.commit()
    
    return {
        "success": True,
        "rule_id": rule.id,
        "message": f"Created rule '{title}' (ID: {rule.id})"
    }

def update_rule_tool(session: Session, rule_id: int, updates: dict):
    """Tool: Update an existing rule."""
    rule = session.get(TutorRule, rule_id)
    if not rule:
        return {"success": False, "error": f"Rule ID {rule_id} not found"}
    
    # Track what changed
    changes = []
    for key, value in updates.items():
        if hasattr(rule, key):
            old_value = getattr(rule, key)
            if old_value != value:
                setattr(rule, key, value)
                changes.append(f"{key}: {old_value} -> {value}")
    
    if not changes:
        return {"success": True, "message": "No changes made"}
    
    rule.updated_by = "ai_admin"
    rule.updated_at = datetime.utcnow()
    session.add(rule)
    session.commit()
    session.refresh(rule)
    
    # Create audit version
    version = TutorRuleVersion(
        rule_id=rule.id,
        scope=rule.scope,
        type=rule.type,
        title=rule.title,
        description=rule.description,
        trigger_condition=rule.trigger_condition,
        action=rule.action,
        priority=rule.priority,
        is_active=rule.is_active,
        changed_by="ai_admin",
        change_reason=f"Updated by AI: {', '.join(changes)}"
    )
    session.add(version)
    session.commit()
    
    return {
        "success": True,
        "message": f"Updated rule ID {rule_id}",
        "changes": changes
    }

def deactivate_rule_tool(session: Session, rule_id: int):
    """Tool: Deactivate a rule."""
    rule = session.get(TutorRule, rule_id)
    if not rule:
        return {"success": False, "error": f"Rule ID {rule_id} not found"}
    
    rule.is_active = False
    rule.updated_by = "ai_admin"
    rule.updated_at = datetime.utcnow()
    session.add(rule)
    session.commit()
    
    # Create audit version
    version = TutorRuleVersion(
        rule_id=rule.id,
        scope=rule.scope,
        type=rule.type,
        title=rule.title,
        description=rule.description,
        trigger_condition=rule.trigger_condition,
        action=rule.action,
        priority=rule.priority,
        is_active=False,
        changed_by="ai_admin",
        change_reason="Deactivated by AI Admin Assistant"
    )
    session.add(version)
    session.commit()
    
    return {
        "success": True,
        "message": f"Deactivated rule '{rule.title}' (ID: {rule_id})"
    }

# Tool definitions for OpenAI
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_rules",
            "description": "List tutor behavior rules with optional filters",
            "parameters": {
                "type": "object",
                "properties": {
                    "scope": {"type": "string", "enum": ["global", "app", "student", "session"], "description": "Filter by scope"},
                    "student_id": {"type": "integer", "description": "Filter by student ID (for student-scoped rules)"},
                    "is_active": {"type": "boolean", "description": "Filter by active status"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_rule",
            "description": "Create a new tutor behavior rule",
            "parameters": {
                "type": "object",
                "properties": {
                    "scope": {"type": "string", "enum": ["global", "app", "student", "session"]},
                    "type": {"type": "string", "enum": ["greeting", "toxicity_warning", "difficulty_adjustment", "language_mode", "other"]},
                    "title": {"type": "string", "description": "Short title for the rule"},
                    "description": {"type": "string", "description": "Detailed description of the rule behavior"},
                    "trigger_condition": {"type": "string", "description": "JSON string describing when the rule applies"},
                    "action": {"type": "string", "description": "JSON string describing what action to take"},
                    "priority": {"type": "integer", "description": "Priority (lower = higher priority)", "default": 0}
                },
                "required": ["scope", "type", "title", "description"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_rule",
            "description": "Update an existing tutor rule",
            "parameters": {
                "type": "object",
                "properties": {
                    "rule_id": {"type": "integer"},
                    "updates": {
                        "type": "object",
                        "description": "Fields to update (title, description, priority, etc.)"
                    }
                },
                "required": ["rule_id", "updates"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "deactivate_rule",
            "description": "Deactivate a tutor rule",
            "parameters": {
                "type": "object",
                "properties": {
                    "rule_id": {"type": "integer"}
                },
                "required": ["rule_id"]
            }
        }
    }
]

def execute_tool_call(session: Session, tool_name: str, tool_args: dict):
    """Execute a tool call and return the result."""
    if tool_name == "list_rules":
        return list_rules_tool(session, **tool_args)
    elif tool_name == "create_rule":
        return create_rule_tool(session, **tool_args)
    elif tool_name == "update_rule":
        return update_rule_tool(session, **tool_args)
    elif tool_name == "deactivate_rule":
        return deactivate_rule_tool(session, **tool_args)
    else:
        return {"error": f"Unknown tool: {tool_name}"}

def process_admin_message(
    admin_user_id: int,
    message_text: str,
    session: Session,
    conversation_id: Optional[int] = None
) -> dict:
    """Process an admin message and return AI response."""
    # Get OpenAI settings
    settings = session.get(AppSettings, 1)
    if not settings or not settings.openai_api_key:
        return {
            "error": "OpenAI API key not configured",
            "conversation_id": conversation_id
        }
    
    # Get or create conversation
    conversation = get_or_create_conversation(session, admin_user_id, conversation_id)
    
    # Save user message
    save_message(session, conversation.id, "human", message_text, "text")
    
    # Get conversation history
    history_statement = select(AdminAIMessage).where(
        AdminAIMessage.conversation_id == conversation.id
    ).order_by(AdminAIMessage.created_at)
    history = session.exec(history_statement).all()
    
    # Build messages for OpenAI
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    for msg in history:
        role = "user" if msg.sender == "human" else "assistant"
        messages.append({"role": role, "content": msg.content})
    
    # Call OpenAI with tool calling
    client = OpenAI(api_key=settings.openai_api_key)
    
    try:
        response = client.chat.completions.create(
            model=settings.default_model,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto"
        )
        
        message = response.choices[0].message
        tool_calls = message.tool_calls
        
        # Execute tool calls if any
        actions_taken = []
        if tool_calls:
            for tool_call in tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)
                
                result = execute_tool_call(session, tool_name, tool_args)
                actions_taken.append({
                    "tool": tool_name,
                    "args": tool_args,
                    "result": result
                })
                
                # Add tool result to messages
                messages.append({
                    "role": "assistant",
                    "content": message.content or "",
                    "tool_calls": [{
                        "id": tool_call.id,
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "arguments": tool_call.function.arguments
                        }
                    }]
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result)
                })
            
            # Get final response after tool execution
            final_response = client.chat.completions.create(
                model=settings.default_model,
                messages=messages
            )
            ai_response = final_response.choices[0].message.content
        else:
            ai_response = message.content
        
        # Save AI message
        save_message(session, conversation.id, "ai", ai_response, "text")
        
        return {
            "conversation_id": conversation.id,
            "ai_response": ai_response,
            "actions_taken": actions_taken
        }
        
    except Exception as e:
        error_msg = f"Error processing request: {str(e)}"
        save_message(session, conversation.id, "ai", error_msg, "system")
        return {
            "conversation_id": conversation.id,
            "error": error_msg
        }
