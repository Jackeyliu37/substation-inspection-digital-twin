uint32 SCHEMA_VERSION=1
uint8 LEVEL_NORMAL=0
uint8 LEVEL_ATTENTION=1
uint8 LEVEL_ALERT=2
uint8 LEVEL_EMERGENCY=3

uint32 schema_version
string asset_id
float32 score_0_100
uint8 level
float32 visual_0_1
float32 temperature_0_1
float32 smoke_0_1
float32 gas_0_1
float32 context_0_1
uint32 confirmation_frames
builtin_interfaces/Time last_observed
string[] evidence_ids
