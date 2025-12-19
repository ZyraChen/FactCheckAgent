"""
LangChain Agents for Debate System
"""

from .pro_agent_lc import create_pro_agent
from .con_agent_lc import create_con_agent
from .judge_agent_lc import create_judge_agent

__all__ = ['create_pro_agent', 'create_con_agent', 'create_judge_agent']
