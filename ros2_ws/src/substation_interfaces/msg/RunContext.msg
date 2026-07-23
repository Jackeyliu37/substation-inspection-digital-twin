uint32 SCHEMA_VERSION=1
uint8 LIFECYCLE_IDLE=0
uint8 LIFECYCLE_STARTING=1
uint8 LIFECYCLE_ACTIVE=2
uint8 LIFECYCLE_ENDING=3
uint8 LIFECYCLE_ENDED=4

uint32 schema_version
std_msgs/Header header
uint64 context_revision
uint8 lifecycle
string run_id
builtin_interfaces/Time started_at
builtin_interfaces/Time ended_at
string transition_command_id
string reason_code
string reason
