from enum import StrEnum


class EntityType(StrEnum):
    TOOL = "tool"
    TASK = "task"
    COMPANY = "company"
    NEWS = "news"
    VIDEO = "video"
    ROBOT = "robot"
    DEVICE = "device"
    MODEL = "model"
    REPOSITORY = "repository"
    MCP = "mcp"
    COLLECTION = "collection"
    PERSONAL = "personal"
    CREATIVE = "creative"


class RelationshipType(StrEnum):
    DEVELOPS = "develops"
    SOLVES = "solves"
    INTEGRATES_WITH = "integrates_with"
    RUNS = "runs"
    PART_OF_COLLECTION = "part_of_collection"
