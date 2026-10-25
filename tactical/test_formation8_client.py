"""Bounded parent request contract for the command-lineage formation backend."""
import test_mission5_client as previous

class CommandLineageClient(previous.BreadcrumbClient):
 family='mission-formation-v8'
