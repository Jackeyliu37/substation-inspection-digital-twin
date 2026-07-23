uint32 SCHEMA_VERSION=1
uint8 STATE_ACCEPTED=0
uint8 STATE_APPLIED=1
uint8 STATE_REJECTED=2
uint8 STATE_EXPIRED=3
uint8 STATE_CANCELLED=4

uint32 schema_version
std_msgs/Header header
string command_id
uint8 state
string error_code
string error_message
