from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.classification import EntityClassifier
from src.models import Entity, EntityType, SourceReference
from src.relationships import RelationshipMapper
from src.utils.ids import generate_entity_id
from src.validation import DatasetValidator

DATA_DIR = PROJECT_ROOT / "data"

TASKS = [
    "Question Answering",
    "Summarization",
    "Code Generation",
    "Image Generation",
    "Video Generation",
    "Speech Recognition",
    "Text To Speech",
    "Machine Translation",
    "Search",
    "Retrieval Augmented Generation",
    "Data Analysis",
    "Meeting Notes",
    "Customer Support",
    "Document Understanding",
    "Object Detection",
    "Image Classification",
    "Robotic Manipulation",
    "Navigation",
    "Workflow Automation",
    "Knowledge Management",
    "Writing Assistance",
    "Research Assistance",
    "Browser Automation",
    "Spreadsheet Automation",
    "Music Generation",
]

COMPANIES = [
    ("OpenAI", "https://openai.com", 2015, "AI research and products", "San Francisco, US"),
    ("Anthropic", "https://anthropic.com", 2021, "AI safety and assistants", "San Francisco, US"),
    ("Google DeepMind", "https://deepmind.google", 2010, "AI research", "London, UK"),
    ("Google", "https://google.com", 1998, "Technology", "Mountain View, US"),
    ("Microsoft", "https://microsoft.com", 1975, "Cloud and productivity", "Redmond, US"),
    ("Meta", "https://about.meta.com", 2004, "Social technology and AI", "Menlo Park, US"),
    ("Mistral AI", "https://mistral.ai", 2023, "AI models", "Paris, France"),
    ("Hugging Face", "https://huggingface.co", 2016, "AI platform", "New York, US"),
    ("Stability AI", "https://stability.ai", 2019, "Generative media", "London, UK"),
    ("Midjourney", "https://midjourney.com", 2022, "Image generation", "San Francisco, US"),
    ("Runway", "https://runwayml.com", 2018, "Creative AI", "New York, US"),
    ("ElevenLabs", "https://elevenlabs.io", 2022, "Speech AI", "New York, US"),
    ("Perplexity", "https://perplexity.ai", 2022, "AI search", "San Francisco, US"),
    ("xAI", "https://x.ai", 2023, "AI assistants", "Burlingame, US"),
    ("Cohere", "https://cohere.com", 2019, "Enterprise AI", "Toronto, Canada"),
    ("NVIDIA", "https://nvidia.com", 1993, "AI hardware", "Santa Clara, US"),
    ("Apple", "https://apple.com", 1976, "Consumer technology", "Cupertino, US"),
    ("Amazon", "https://amazon.com", 1994, "Cloud and commerce", "Seattle, US"),
    ("Adobe", "https://adobe.com", 1982, "Creative software", "San Jose, US"),
    ("Notion", "https://notion.so", 2013, "Productivity software", "San Francisco, US"),
    ("GitHub", "https://github.com", 2008, "Developer tools", "San Francisco, US"),
    ("LangChain", "https://langchain.com", 2022, "AI developer tools", "San Francisco, US"),
    ("Anysphere", "https://anysphere.co", 2022, "Developer tools", "San Francisco, US"),
    ("Character.AI", "https://character.ai", 2021, "AI companions", "Menlo Park, US"),
    ("Figure AI", "https://figure.ai", 2022, "Humanoid robotics", "Sunnyvale, US"),
]

TOOLS = [
    ("ChatGPT", "OpenAI", "https://chatgpt.com", ["Question Answering", "Writing Assistance", "Data Analysis"]),
    ("Claude", "Anthropic", "https://claude.ai", ["Question Answering", "Writing Assistance", "Code Generation"]),
    ("Gemini", "Google DeepMind", "https://gemini.google.com", ["Question Answering", "Research Assistance"]),
    ("Microsoft Copilot", "Microsoft", "https://copilot.microsoft.com", ["Writing Assistance", "Code Generation"]),
    ("Meta AI", "Meta", "https://meta.ai", ["Question Answering", "Writing Assistance"]),
    ("Le Chat", "Mistral AI", "https://chat.mistral.ai", ["Question Answering"]),
    ("HuggingChat", "Hugging Face", "https://huggingface.co/chat", ["Question Answering"]),
    ("Perplexity", "Perplexity", "https://perplexity.ai", ["Search", "Research Assistance"]),
    ("Grok", "xAI", "https://grok.com", ["Question Answering"]),
    ("Command R", "Cohere", "https://cohere.com/command", ["Retrieval Augmented Generation", "Search"]),
    ("Cursor", "Anysphere", "https://cursor.com", ["Code Generation"]),
    ("GitHub Copilot", "GitHub", "https://github.com/features/copilot", ["Code Generation"]),
    ("LangSmith", "LangChain", "https://smith.langchain.com", ["Workflow Automation"]),
    ("LangGraph Platform", "LangChain", "https://langchain.com/langgraph", ["Workflow Automation"]),
    ("NotebookLM", "Google", "https://notebooklm.google", ["Knowledge Management", "Research Assistance"]),
    ("Notion AI", "Notion", "https://notion.so/product/ai", ["Writing Assistance", "Knowledge Management"]),
    ("Adobe Firefly", "Adobe", "https://firefly.adobe.com", ["Image Generation"]),
    ("Midjourney", "Midjourney", "https://midjourney.com", ["Image Generation"]),
    ("Runway", "Runway", "https://runwayml.com", ["Video Generation", "Image Generation"]),
    ("ElevenLabs Studio", "ElevenLabs", "https://elevenlabs.io", ["Text To Speech", "Speech Recognition"]),
    ("Stable Assistant", "Stability AI", "https://stability.ai/stable-assistant", ["Image Generation"]),
    ("Amazon Q", "Amazon", "https://aws.amazon.com/q", ["Code Generation", "Data Analysis"]),
    ("Apple Intelligence", "Apple", "https://apple.com/apple-intelligence", ["Writing Assistance", "Productivity"]),
    ("Character.AI", "Character.AI", "https://character.ai", ["Question Answering"]),
    ("NVIDIA NIM", "NVIDIA", "https://nvidia.com/en-us/ai", ["Workflow Automation"]),
    ("OpenAI API", "OpenAI", "https://platform.openai.com", ["Workflow Automation", "Code Generation"]),
    ("Anthropic API", "Anthropic", "https://console.anthropic.com", ["Workflow Automation"]),
    ("Gemini API", "Google", "https://ai.google.dev", ["Workflow Automation"]),
    ("Mistral La Plateforme", "Mistral AI", "https://console.mistral.ai", ["Workflow Automation"]),
    ("Hugging Face Inference Endpoints", "Hugging Face", "https://huggingface.co/inference-endpoints", ["Workflow Automation"]),
    ("Cohere Toolkit", "Cohere", "https://cohere.com/toolkit", ["Retrieval Augmented Generation"]),
    ("OpenAI Codex", "OpenAI", "https://openai.com/codex", ["Code Generation"]),
    ("Gemini Code Assist", "Google", "https://cloud.google.com/products/gemini/code-assist", ["Code Generation"]),
    ("Azure AI Foundry", "Microsoft", "https://ai.azure.com", ["Workflow Automation"]),
    ("Amazon Bedrock", "Amazon", "https://aws.amazon.com/bedrock", ["Workflow Automation"]),
    ("Google Vertex AI", "Google", "https://cloud.google.com/vertex-ai", ["Workflow Automation"]),
    ("Meta AI Studio", "Meta", "https://ai.meta.com/ai-studio", ["Workflow Automation"]),
    ("NVIDIA Omniverse", "NVIDIA", "https://nvidia.com/omniverse", ["Video Generation"]),
    ("Adobe Express AI", "Adobe", "https://adobe.com/express", ["Image Generation"]),
    ("Runway Gen-3", "Runway", "https://runwayml.com/research/introducing-gen-3-alpha", ["Video Generation"]),
    ("ElevenLabs Dubbing", "ElevenLabs", "https://elevenlabs.io/dubbing", ["Machine Translation", "Text To Speech"]),
    ("Perplexity Pages", "Perplexity", "https://perplexity.ai/pages", ["Research Assistance", "Writing Assistance"]),
    ("Claude Code", "Anthropic", "https://anthropic.com/claude-code", ["Code Generation"]),
    ("Deep Research", "OpenAI", "https://openai.com", ["Research Assistance"]),
    ("Veo", "Google DeepMind", "https://deepmind.google/models/veo", ["Video Generation"]),
]

MODELS = [
    ("GPT-4o", "OpenAI", "text-generation", "openai", "https://openai.com/index/hello-gpt-4o"),
    ("GPT-4.1", "OpenAI", "text-generation", "openai", "https://openai.com/models/gpt-4.1"),
    ("o3", "OpenAI", "text-generation", "openai", "https://openai.com/models/o3"),
    ("Claude 3.5 Sonnet", "Anthropic", "text-generation", "anthropic", "https://anthropic.com/claude/sonnet"),
    ("Claude 3 Opus", "Anthropic", "text-generation", "anthropic", "https://anthropic.com/claude/opus"),
    ("Gemini 2.5 Pro", "Google DeepMind", "text-generation", "google", "https://deepmind.google/models/gemini/pro"),
    ("Gemini 2.0 Flash", "Google DeepMind", "text-generation", "google", "https://deepmind.google/models/gemini/flash"),
    ("Llama 3.1 8B", "Meta", "text-generation", "llama-license", "https://huggingface.co/meta-llama/Llama-3.1-8B"),
    ("Llama 3.1 70B", "Meta", "text-generation", "llama-license", "https://huggingface.co/meta-llama/Llama-3.1-70B"),
    ("Mistral Large", "Mistral AI", "text-generation", "mistral", "https://mistral.ai"),
    ("Mixtral 8x7B", "Mistral AI", "text-generation", "apache-2.0", "https://huggingface.co/mistralai/Mixtral-8x7B-Instruct-v0.1"),
    ("Command R+", "Cohere", "text-generation", "cohere", "https://cohere.com/command"),
    ("Aya Expanse", "Cohere", "text-generation", "cohere", "https://cohere.com/research"),
    ("Stable Diffusion XL", "Stability AI", "text-to-image", "openrail", "https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0"),
    ("Stable Diffusion 3", "Stability AI", "text-to-image", "stability", "https://stability.ai"),
    ("Midjourney V6", "Midjourney", "text-to-image", "midjourney", "https://midjourney.com"),
    ("Runway Gen-3 Alpha", "Runway", "text-to-video", "runway", "https://runwayml.com/research/introducing-gen-3-alpha"),
    ("Eleven Multilingual v2", "ElevenLabs", "text-to-speech", "elevenlabs", "https://elevenlabs.io"),
    ("Whisper", "OpenAI", "automatic-speech-recognition", "mit", "https://github.com/openai/whisper"),
    ("CLIP", "OpenAI", "image-classification", "mit", "https://github.com/openai/CLIP"),
    ("DINOv2", "Meta", "image-classification", "apache-2.0", "https://github.com/facebookresearch/dinov2"),
    ("SAM 2", "Meta", "object-detection", "apache-2.0", "https://ai.meta.com/sam2"),
    ("Qwen3 0.6B", "Alibaba", "text-generation", "apache-2.0", "https://huggingface.co/Qwen/Qwen3-0.6B"),
    ("Phi-4", "Microsoft", "text-generation", "mit", "https://huggingface.co/microsoft"),
    ("Florence-2", "Microsoft", "image-classification", "mit", "https://huggingface.co/microsoft/Florence-2-base"),
    ("Gemma 2", "Google", "text-generation", "gemma", "https://huggingface.co/google/gemma-2-2b"),
    ("PaliGemma", "Google", "image-classification", "gemma", "https://huggingface.co/google/paligemma-3b-pt-224"),
    ("BERT", "Google", "text-classification", "apache-2.0", "https://huggingface.co/google-bert/bert-base-uncased"),
    ("T5", "Google", "text-generation", "apache-2.0", "https://huggingface.co/google-t5/t5-base"),
    ("BGE Large", "Hugging Face", "sentence-similarity", "mit", "https://huggingface.co/BAAI/bge-large-en-v1.5"),
    ("E5 Large", "Microsoft", "sentence-similarity", "mit", "https://huggingface.co/intfloat/e5-large-v2"),
    ("MusicGen", "Meta", "text-to-audio", "mit", "https://github.com/facebookresearch/audiocraft"),
    ("Suno Bark", "Suno", "text-to-speech", "mit", "https://github.com/suno-ai/bark"),
    ("YOLOv8", "Ultralytics", "object-detection", "agpl-3.0", "https://github.com/ultralytics/ultralytics"),
    ("Segment Anything", "Meta", "object-detection", "apache-2.0", "https://github.com/facebookresearch/segment-anything"),
]

REPOSITORIES = [
    ("langchain", "langchain-ai", "https://github.com/langchain-ai/langchain", "Python", ["llm", "agents", "rag"]),
    ("langgraph", "langchain-ai", "https://github.com/langchain-ai/langgraph", "Python", ["agents"]),
    ("llama_index", "run-llama", "https://github.com/run-llama/llama_index", "Python", ["rag"]),
    ("transformers", "huggingface", "https://github.com/huggingface/transformers", "Python", ["models"]),
    ("diffusers", "huggingface", "https://github.com/huggingface/diffusers", "Python", ["image-generation"]),
    ("peft", "huggingface", "https://github.com/huggingface/peft", "Python", ["fine-tuning"]),
    ("openai-python", "openai", "https://github.com/openai/openai-python", "Python", ["sdk"]),
    ("openai-cookbook", "openai", "https://github.com/openai/openai-cookbook", "Jupyter Notebook", ["examples"]),
    ("anthropic-sdk-python", "anthropics", "https://github.com/anthropics/anthropic-sdk-python", "Python", ["sdk"]),
    ("mcp", "modelcontextprotocol", "https://github.com/modelcontextprotocol/modelcontextprotocol", "TypeScript", ["mcp"]),
    ("servers", "modelcontextprotocol", "https://github.com/modelcontextprotocol/servers", "TypeScript", ["mcp"]),
    ("semantic-kernel", "microsoft", "https://github.com/microsoft/semantic-kernel", "C#", ["agents"]),
    ("autogen", "microsoft", "https://github.com/microsoft/autogen", "Python", ["agents"]),
    ("guidance", "guidance-ai", "https://github.com/guidance-ai/guidance", "Python", ["prompting"]),
    ("dspy", "stanfordnlp", "https://github.com/stanfordnlp/dspy", "Python", ["optimization"]),
    ("vllm", "vllm-project", "https://github.com/vllm-project/vllm", "Python", ["inference"]),
    ("ollama", "ollama", "https://github.com/ollama/ollama", "Go", ["local-models"]),
    ("llama.cpp", "ggml-org", "https://github.com/ggml-org/llama.cpp", "C++", ["local-models"]),
    ("ray", "ray-project", "https://github.com/ray-project/ray", "Python", ["distributed"]),
    ("gradio", "gradio-app", "https://github.com/gradio-app/gradio", "Python", ["apps"]),
    ("streamlit", "streamlit", "https://github.com/streamlit/streamlit", "Python", ["apps"]),
    ("fastapi", "fastapi", "https://github.com/fastapi/fastapi", "Python", ["api"]),
    ("pytorch", "pytorch", "https://github.com/pytorch/pytorch", "Python", ["machine-learning"]),
    ("tensorflow", "tensorflow", "https://github.com/tensorflow/tensorflow", "C++", ["machine-learning"]),
    ("jax", "jax-ml", "https://github.com/jax-ml/jax", "Python", ["machine-learning"]),
    ("scikit-learn", "scikit-learn", "https://github.com/scikit-learn/scikit-learn", "Python", ["machine-learning"]),
    ("opencv", "opencv", "https://github.com/opencv/opencv", "C++", ["computer-vision"]),
    ("ultralytics", "ultralytics", "https://github.com/ultralytics/ultralytics", "Python", ["computer-vision"]),
    ("segment-anything", "facebookresearch", "https://github.com/facebookresearch/segment-anything", "Python", ["computer-vision"]),
    ("audiocraft", "facebookresearch", "https://github.com/facebookresearch/audiocraft", "Python", ["audio"]),
    ("whisper", "openai", "https://github.com/openai/whisper", "Python", ["speech"]),
    ("stable-diffusion-webui", "AUTOMATIC1111", "https://github.com/AUTOMATIC1111/stable-diffusion-webui", "Python", ["image-generation"]),
    ("comfyui", "comfyanonymous", "https://github.com/comfyanonymous/ComfyUI", "Python", ["image-generation"]),
    ("crewAI", "crewAIInc", "https://github.com/crewAIInc/crewAI", "Python", ["agents"]),
    ("haystack", "deepset-ai", "https://github.com/deepset-ai/haystack", "Python", ["rag"]),
]

DEVICES = [
    ("NVIDIA Jetson Orin", "NVIDIA", "https://developer.nvidia.com/embedded/jetson-agx-orin", ["Llama 3.1 8B"]),
    ("NVIDIA DGX H100", "NVIDIA", "https://nvidia.com/en-us/data-center/dgx-h100", ["Llama 3.1 70B"]),
    ("NVIDIA Grace Blackwell", "NVIDIA", "https://nvidia.com/en-us/data-center/gb200-nvl72", ["GPT-4o"]),
    ("Apple Vision Pro", "Apple", "https://apple.com/apple-vision-pro", ["Gemma 2"]),
    ("iPhone 16 Pro", "Apple", "https://apple.com/iphone-16-pro", ["Gemma 2"]),
    ("Mac Studio", "Apple", "https://apple.com/mac-studio", ["Whisper"]),
    ("AWS Trainium", "Amazon", "https://aws.amazon.com/machine-learning/trainium", ["Llama 3.1 70B"]),
    ("AWS Inferentia", "Amazon", "https://aws.amazon.com/machine-learning/inferentia", ["Mixtral 8x7B"]),
    ("Google TPU v5p", "Google", "https://cloud.google.com/tpu", ["Gemini 2.0 Flash"]),
    ("Microsoft Azure ND H100 v5", "Microsoft", "https://azure.microsoft.com/products/virtual-machines", ["Phi-4"]),
    ("Meta Quest 3", "Meta", "https://meta.com/quest/quest-3", ["SAM 2"]),
    ("Rabbit R1", "Rabbit", "https://rabbit.tech", ["Whisper"]),
]

ROBOTS = [
    ("Figure 02", "Figure AI", "https://figure.ai"),
    ("Tesla Optimus", "Tesla", "https://tesla.com/AI"),
    ("Boston Dynamics Atlas", "Boston Dynamics", "https://bostondynamics.com/atlas"),
    ("Agility Digit", "Agility Robotics", "https://agilityrobotics.com"),
    ("Unitree H1", "Unitree", "https://unitree.com"),
    ("Apptronik Apollo", "Apptronik", "https://apptronik.com"),
    ("Sanctuary Phoenix", "Sanctuary AI", "https://sanctuary.ai"),
    ("1X NEO", "1X", "https://1x.tech"),
    ("Covariant RFM-1", "Covariant", "https://covariant.ai"),
    ("Skild AI Robot Brain", "Skild AI", "https://skild.ai"),
    ("ANYbotics ANYmal", "ANYbotics", "https://anybotics.com"),
    ("Robust.AI Carter", "Robust.AI", "https://robust.ai"),
]

PERSONAL = [
    ("Pi", "Inflection", "https://pi.ai"),
    ("Replika", "Luka", "https://replika.com"),
    ("Character.AI Assistant", "Character.AI", "https://character.ai"),
    ("Personal.ai", "Personal AI", "https://personal.ai"),
    ("You.com Assistant", "You.com", "https://you.com"),
    ("Poe", "Quora", "https://poe.com"),
    ("Khanmigo", "Khan Academy", "https://khanacademy.org/khan-labs"),
    ("GrammarlyGO", "Grammarly", "https://grammarly.com/ai"),
    ("Otter AI Chat", "Otter.ai", "https://otter.ai"),
    ("Fathom AI", "Fathom", "https://fathom.video"),
    ("Mem", "Mem", "https://mem.ai"),
    ("Rewind", "Rewind", "https://rewind.ai"),
]

CREATIVE = [
    ("DALL-E 3", "OpenAI", "https://openai.com/dall-e-3", "Image Generation"),
    ("Midjourney V6", "Midjourney", "https://midjourney.com", "Image Generation"),
    ("Stable Diffusion", "Stability AI", "https://stability.ai", "Image Generation"),
    ("Adobe Firefly Image Model", "Adobe", "https://firefly.adobe.com", "Image Generation"),
    ("Runway Gen-3", "Runway", "https://runwayml.com/research/introducing-gen-3-alpha", "Video Generation"),
    ("Veo", "Google DeepMind", "https://deepmind.google/models/veo", "Video Generation"),
    ("Sora", "OpenAI", "https://openai.com/sora", "Video Generation"),
    ("Pika", "Pika", "https://pika.art", "Video Generation"),
    ("Luma Dream Machine", "Luma AI", "https://lumalabs.ai/dream-machine", "Video Generation"),
    ("Suno", "Suno", "https://suno.com", "Music Generation"),
    ("Udio", "Udio", "https://udio.com", "Music Generation"),
    ("ElevenLabs Voice Design", "ElevenLabs", "https://elevenlabs.io", "Text To Speech"),
    ("Canva Magic Studio", "Canva", "https://canva.com/magic", "Image Generation"),
    ("Krea AI", "Krea", "https://krea.ai", "Image Generation"),
    ("Ideogram", "Ideogram", "https://ideogram.ai", "Image Generation"),
]

COLLECTIONS = [
    ("AI Agents Collection", "https://github.com/e2b-dev/awesome-ai-agents", "agents"),
    ("RAG Systems Collection", "https://github.com/NirDiamant/RAG_Techniques", "rag"),
    ("Open Models Collection", "https://huggingface.co/models", "open-source"),
    ("MCP Servers Collection", "https://github.com/modelcontextprotocol/servers", "developer-tools"),
    ("AI Hardware Collection", "https://nvidia.com/en-us/ai", "hardware"),
    ("Robotics Collection", "https://spectrum.ieee.org/robotics", "robotics"),
    ("Generative Video Collection", "https://runwayml.com/research", "video-generation"),
    ("Generative Image Collection", "https://stability.ai", "image-generation"),
    ("Speech AI Collection", "https://elevenlabs.io", "speech"),
    ("Computer Vision Collection", "https://paperswithcode.com/task/object-detection", "computer-vision"),
    ("Developer Tooling Collection", "https://github.com/topics/llm", "developer-tools"),
    ("AI Research Collection", "https://arxiv.org/list/cs.AI/recent", "research"),
]

MCP_SERVERS = [
    ("GitHub MCP Server", "GitHub", "https://github.com/github/github-mcp-server", ["GitHub Copilot"]),
    ("Filesystem MCP Server", "Model Context Protocol", "https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem", ["Claude"]),
    ("Postgres MCP Server", "Model Context Protocol", "https://github.com/modelcontextprotocol/servers/tree/main/src/postgres", ["Claude"]),
    ("Slack MCP Server", "Model Context Protocol", "https://github.com/modelcontextprotocol/servers/tree/main/src/slack", ["Claude"]),
    ("Google Drive MCP Server", "Model Context Protocol", "https://github.com/modelcontextprotocol/servers/tree/main/src/gdrive", ["Gemini"]),
    ("Puppeteer MCP Server", "Model Context Protocol", "https://github.com/modelcontextprotocol/servers/tree/main/src/puppeteer", ["Claude"]),
    ("Brave Search MCP Server", "Model Context Protocol", "https://github.com/modelcontextprotocol/servers/tree/main/src/brave-search", ["Perplexity"]),
    ("Memory MCP Server", "Model Context Protocol", "https://github.com/modelcontextprotocol/servers/tree/main/src/memory", ["Claude"]),
    ("Fetch MCP Server", "Model Context Protocol", "https://github.com/modelcontextprotocol/servers/tree/main/src/fetch", ["ChatGPT"]),
    ("Sentry MCP Server", "Sentry", "https://github.com/getsentry/sentry-mcp", ["Cursor"]),
    ("Stripe MCP Server", "Stripe", "https://github.com/stripe/agent-toolkit", ["ChatGPT"]),
    ("Cloudflare MCP Server", "Cloudflare", "https://github.com/cloudflare/mcp-server-cloudflare", ["Claude"]),
    ("Atlassian MCP Server", "Atlassian", "https://www.atlassian.com", ["Claude"]),
    ("Linear MCP Server", "Linear", "https://linear.app", ["Cursor"]),
    ("Notion MCP Server", "Notion", "https://notion.so", ["Notion AI"]),
    ("Airtable MCP Server", "Airtable", "https://airtable.com", ["ChatGPT"]),
    ("Supabase MCP Server", "Supabase", "https://supabase.com", ["Cursor"]),
    ("Browserbase MCP Server", "Browserbase", "https://browserbase.com", ["Claude"]),
    ("Playwright MCP Server", "Microsoft", "https://github.com/microsoft/playwright-mcp", ["Claude"]),
    ("Figma MCP Server", "Figma", "https://figma.com", ["Claude"]),
]

NEWS = [
    "OpenAI announces GPT-4o",
    "Anthropic introduces Claude 3.5 Sonnet",
    "Google DeepMind shares Gemini updates",
    "Meta releases Llama model updates",
    "Mistral AI expands model platform",
    "Hugging Face updates model hub",
    "NVIDIA launches AI computing platform",
    "Runway introduces Gen-3 Alpha",
    "ElevenLabs expands speech tools",
    "Adobe updates Firefly models",
    "Microsoft expands Copilot",
    "Amazon expands Bedrock",
    "Apple introduces Apple Intelligence",
    "Perplexity launches research features",
    "LangChain expands LangGraph",
    "GitHub expands Copilot features",
    "Stability AI updates image models",
    "Figure AI demonstrates humanoid progress",
    "Google announces Veo video model",
    "OpenAI introduces Sora",
]

VIDEOS = [
    "OpenAI GPT-4o demo",
    "Anthropic Claude product tour",
    "Google Gemini keynote",
    "NVIDIA AI keynote",
    "Meta Llama overview",
    "Mistral AI platform overview",
    "Hugging Face model hub tutorial",
    "Runway Gen-3 examples",
    "ElevenLabs voice demo",
    "Adobe Firefly tutorial",
    "LangChain agents walkthrough",
    "GitHub Copilot coding demo",
    "Perplexity research demo",
    "Figure robot demo",
    "Apple Intelligence overview",
]


def source(name: str, url: str) -> list[SourceReference]:
    return [SourceReference(name=name, url=url)]


def entity(entity_type: EntityType, name: str, url: str, **kwargs: Any) -> Entity:
    return Entity(
        id=generate_entity_id(str(entity_type), f"{url}#{name}"),
        entity_type=entity_type,
        name=name,
        url=url,
        sources=source(kwargs.pop("source_name", "Official source"), url),
        **kwargs,
    )


def build_entities() -> list[Entity]:
    entities: list[Entity] = []
    classifier = EntityClassifier()

    for name in TASKS:
        slug = name.lower().replace(" ", "-")
        entities.append(
            entity(
                EntityType.TASK,
                name,
                f"https://{slug}.tasks.ai-orbit.example",
                description=f"Representative AI task: {name}.",
                categories=[],
                metadata={"curated": True},
                source_name="AI Orbit curated task taxonomy",
            )
        )

    for name, url, year, sector, hq in COMPANIES:
        entities.append(
            entity(
                EntityType.COMPANY,
                name,
                url,
                description=f"{name} is represented in the AI ecosystem dataset.",
                metadata={
                    "founding_year": year,
                    "industry_sector": sector,
                    "headquarters": hq,
                    "official_domain": url.split("//", 1)[1].split("/", 1)[0],
                },
            )
        )

    for name, provider, url, tasks in TOOLS:
        entities.append(
            entity(
                EntityType.TOOL,
                name,
                url,
                description=f"{name} is an AI tool for {', '.join(tasks).lower()}.",
                metadata={"provider": provider, "tasks": tasks},
            )
        )

    for name, provider, task, license_name, url in MODELS:
        entities.append(
            entity(
                EntityType.MODEL,
                name,
                url,
                description=f"{name} is a representative AI model from {provider}.",
                metadata={
                    "provider": provider,
                    "license": license_name,
                    "modalities": ["text"] if "image" not in task and "speech" not in task and "audio" not in task else ["multimodal"],
                    "pipeline_task": task,
                    "downloads": None,
                    "last_updated": "2026-08-17",
                },
            )
        )

    for name, owner, url, language, topics in REPOSITORIES:
        entities.append(
            entity(
                EntityType.REPOSITORY,
                name,
                url,
                description=f"{name} is a representative open-source AI repository.",
                metadata={
                    "owner": owner,
                    "stars": None,
                    "primary_language": language,
                    "last_updated": "2026-08-17",
                    "topics": topics,
                },
            )
        )

    for name, provider, url, models in DEVICES:
        entities.append(
            entity(
                EntityType.DEVICE,
                name,
                url,
                description=f"{name} is AI hardware or an AI-capable device.",
                metadata={"provider": provider, "runs_models": models},
            )
        )

    for name, provider, url in ROBOTS:
        entities.append(
            entity(
                EntityType.ROBOT,
                name,
                url,
                description=f"{name} is a representative robotics entity.",
                metadata={"provider": provider},
            )
        )

    for name, provider, url in PERSONAL:
        entities.append(
            entity(
                EntityType.PERSONAL,
                name,
                url,
                description=f"{name} is a personal AI assistant or companion.",
                metadata={"provider": provider},
            )
        )

    for name, provider, url, task in CREATIVE:
        entities.append(
            entity(
                EntityType.CREATIVE,
                name,
                url,
                description=f"{name} is a creative AI system for {task.lower()}.",
                metadata={"provider": provider, "tasks": [task]},
            )
        )

    for name, url, category in COLLECTIONS:
        entities.append(
            entity(
                EntityType.COLLECTION,
                name,
                url,
                description=f"{name} groups representative AI ecosystem resources.",
                categories=[category],
                metadata={"curated": True},
            )
        )

    for name, provider, url, tools in MCP_SERVERS:
        entities.append(
            entity(
                EntityType.MCP,
                name,
                url,
                description=f"{name} exposes tools through the Model Context Protocol.",
                metadata={
                    "provider": provider,
                    "installation_method": "repository or provider documentation",
                    "runtime_requirements": ["node", "python"],
                    "repository_url": url,
                    "supported_tools": tools,
                },
            )
        )

    for index, title in enumerate(NEWS, start=1):
        slug = title.lower().replace(" ", "-").replace(".", "")
        entities.append(
            entity(
                EntityType.NEWS,
                title,
                f"https://news-{index:02d}.ai-orbit.example/{slug}",
                description=f"Representative AI ecosystem news item: {title}.",
                metadata={"publisher": "AI Orbit curated news", "published_at": f"2026-08-{index:02d}"},
                source_name="AI Orbit curated news",
            )
        )

    for index, title in enumerate(VIDEOS, start=1):
        slug = title.lower().replace(" ", "-")
        entities.append(
            entity(
                EntityType.VIDEO,
                title,
                f"https://video-{index:02d}.ai-orbit.example/watch/{slug}",
                description=f"Representative AI video: {title}.",
                metadata={"channel": "AI Orbit curated video index", "video_id": f"aiorbit{index:04d}", "slug": slug},
                source_name="AI Orbit curated video index",
            )
        )

    return classifier.classify_many(entities)


def export_dataset() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    entities = build_entities()
    relationships = RelationshipMapper().map_relationships(entities)
    report = DatasetValidator(relaxed=False).validate(
        entities,
        relationships,
        raw_records=len(entities),
    )

    (DATA_DIR / "entities.json").write_text(
        json.dumps([entity.model_dump(mode="json") for entity in entities], indent=2) + "\n",
        encoding="utf-8",
    )
    (DATA_DIR / "relationships.json").write_text(
        json.dumps([relationship.model_dump(mode="json") for relationship in relationships], indent=2) + "\n",
        encoding="utf-8",
    )
    (DATA_DIR / "validation_report.json").write_text(
        json.dumps(report.model_dump(mode="json"), indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"entities={len(entities)}")
    print(f"relationships={len(relationships)}")
    print(f"errors={len(report.errors)}")
    print(f"relationship_errors={len(report.relationship_errors)}")
    print(f"warnings={len(report.warnings)}")
    if not report.success:
        raise SystemExit(1)


if __name__ == "__main__":
    export_dataset()
