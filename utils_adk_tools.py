#!/usr/bin/env python3
"""
ADK Tools Integration Utilities for Persona V3 Orchestrator
Provides utilities for integrating Google ADK tools into agents.
"""

import logging
from typing import List, Optional, Any

logger = logging.getLogger(__name__)

# Try to import ADK tools
try:
    from google.adk.tools import google_search
    ADK_TOOLS_AVAILABLE = True
except ImportError:
    ADK_TOOLS_AVAILABLE = False
    google_search = None

# Try to import BigQuery tools (optional, requires additional setup)
try:
    from google.adk.tools.bigquery import BigQueryToolset
    BIGQUERY_AVAILABLE = True
except ImportError:
    BIGQUERY_AVAILABLE = False
    BigQueryToolset = None


def get_google_search_tool():
    """
    Get Google Search tool from ADK if available.
    
    Returns:
        google_search tool instance or None if not available
    """
    if ADK_TOOLS_AVAILABLE and google_search:
        try:
            return google_search
        except Exception as e:
            logger.warning(f"Failed to initialize Google Search tool: {e}")
            return None
    return None


def get_bigquery_toolset(
    project_id: Optional[str] = None,
    dataset_id: Optional[str] = None,
    location: Optional[str] = None
):
    """
    Get BigQuery Toolset from ADK if available.
    
    Args:
        project_id: Google Cloud project ID (optional, uses default if not provided)
        dataset_id: BigQuery dataset ID (optional)
        location: BigQuery dataset location (optional, e.g., 'US', 'EU')
    
    Returns:
        BigQueryToolset instance or None if not available
        
    Note:
        BigQuery integration is optional and requires:
        - google-adk package with BigQuery support
        - Google Cloud credentials configured
        - Appropriate BigQuery permissions
        
    Example:
        ```python
        bigquery = get_bigquery_toolset(
            project_id="my-project",
            dataset_id="analytics"
        )
        if bigquery:
            # Add to agent tools
            agent.tools.append(bigquery)
        ```
    """
    if not BIGQUERY_AVAILABLE or BigQueryToolset is None:
        logger.debug("BigQuery Toolset not available (package not installed or not supported)")
        return None
    
    try:
        # Initialize BigQueryToolset with optional parameters
        kwargs = {}
        if project_id:
            kwargs['project_id'] = project_id
        if dataset_id:
            kwargs['dataset_id'] = dataset_id
        if location:
            kwargs['location'] = location
        
        toolset = BigQueryToolset(**kwargs) if kwargs else BigQueryToolset()
        logger.info("BigQuery Toolset initialized successfully")
        return toolset
    except Exception as e:
        logger.warning(f"Failed to initialize BigQuery Toolset: {e}")
        logger.warning("Make sure Google Cloud credentials are configured correctly")
        return None


def get_adk_tools_for_agent(agent_name: str) -> List[Any]:
    """
    Get list of ADK tools appropriate for a specific agent.
    
    Args:
    agent_name: Name of the agent (e.g., 'lucim_operation_synthesizer')
        
    Returns:
        List of ADK tools to add to the agent
    """
    tools = []
    
    if not ADK_TOOLS_AVAILABLE:
        return tools
    
    # Add Google Search tool to LUCIM Environment Synthesizer for context enhancement
    if agent_name == "lucim_operation_synthesizer":
        search_tool = get_google_search_tool()
        if search_tool:
            tools.append(search_tool)
            logger.info(f"[ADK] Added Google Search tool to {agent_name}")
    
    # Optional: Add BigQuery for analytics agents
    # if agent_name == "lucim_scenario_synthesizer":
    #     bigquery = get_bigquery_toolset()
    #     if bigquery:
    #         tools.append(bigquery)
    #         logger.info(f"Added BigQuery toolset to {agent_name}")
    
    # Future: Add more tools for other agents as needed
    
    return tools


def configure_agent_with_adk_tools(agent_instance, agent_name: str) -> bool:
    """
    Configure an agent instance with appropriate ADK tools.
    
    Args:
        agent_instance: Agent instance to configure
        agent_name: Name of the agent
        
    Returns:
        True if tools were added, False otherwise
    """
    if not ADK_TOOLS_AVAILABLE:
        logger.info(f"[ADK] Tools not available for {agent_name} (ADK_TOOLS_AVAILABLE=False)")
        return False
    
    tools = get_adk_tools_for_agent(agent_name)
    
    if not tools:
        logger.debug(f"[ADK] No tools configured for {agent_name} (agent not in tool configuration list)")
        return False
    
    # Log tool names being added
    tool_names = [getattr(tool, '__name__', type(tool).__name__) for tool in tools]
    logger.info(f"[ADK] Configuring {agent_name} with {len(tools)} ADK tool(s): {', '.join(tool_names)}")
    
    # Add tools to agent if it supports tools attribute
    if hasattr(agent_instance, 'tools'):
        if agent_instance.tools is None:
            agent_instance.tools = []
        agent_instance.tools.extend(tools)
        logger.info(f"[ADK] Successfully added {len(tools)} tool(s) to {agent_name} via tools attribute")
        return True
    elif hasattr(agent_instance, 'add_tool'):
        for tool in tools:
            agent_instance.add_tool(tool)
        logger.info(f"[ADK] Successfully added {len(tools)} tool(s) to {agent_name} via add_tool() method")
        return True
    else:
        logger.warning(f"[ADK] Agent {agent_name} does not support tools configuration (no 'tools' attribute or 'add_tool' method)")
        return False

