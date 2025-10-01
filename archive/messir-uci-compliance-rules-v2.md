# **Messir-Compliance Rules**

1. PLANT_UML_SEQUENCE_DIAGRAM. A Messir use case instance **must be represented as a UML Sequence Diagram** using strictly plantUML textual syntax.

2. BLANK_LINES_ALLOWED. Blank lines are allowed and must be ignored.

3. SYSTEM_PARTICIPANT. The System participant is a special kind of participant. It must be declared firstly, before all the other participants. There must be exactly one System participant per diagram. It must be declared as a plantUML participant, with a rectangle shape and using "participant System" unlike other participants.

4. PARTICIPANTS_AFTER_SYSTEM_PARTICIPANT. After the system participant instance declaration, all the other participants are declared. Participants instances are modelled as PlantUML participants with a rectangle-shape.

5. PARTICIPANTS_SYNTAX_1. Each participant must be modelled using this plantUML syntax : participant "theParticipantName:actParticipantType" as theParticipantName. e.g., participant "theCreator:actMsrCreator" as theCreator. Another example : participant "chris:actEcologist" as chris

6. PARTICIPANTS_SYNTAX_2. All participants names and types are assigned human-readable identifier in camelCase and are prefixed with "act" (e.g., actAdministrator)

7. MSG_FROM_TO_SYSTEM_ONLY. Messages must be from, or to, the system participant.

8. MSG_NOT_FROM_TO_PARTICIPANT. It is forbidden to model messages from an participant to another participant.

9. SELF_LOOP_EVENT_HANDLING. 
- Self-loop events occur when a participant (Actor or System) sends a message to itself
- Self-loops (System → System and Actor → Actor) are forbidden and must be replaced
- Replacement strategy: Create an actor that can initiate the event
- Example: System setup self-loop becomes actSystemCreator → System: oeSetup()
- **Note**: All self-loops are forbidden regardless of participant type

10. EVENT_DIRECTION_CONVENTION.
- ieX: System sends message TO actor (System → Actor) - Input Event TO actor
- oeX: Actor sends message TO System (Actor → System) - Output Event FROM actor TO System
- All messages must follow this direction convention
- **Note**: The "ie"/"oe" prefix refers to the actor's perspective, not the system's perspective

11.  MSG_IE_SYNTAX. All ie messages names are prefixed with "ie" . ie message names may be generic. ie messages must be modeled using dashed arrows and following this structure:

system --> theParticipant : ieMessageName(parameters)

for example : system --> jen : ieValidationFromTownHall()

another example : system --> jen : ieMessage("Congratulations jen for your 6-years mandate as a major of the town !")

12.  MSG_OE_SYNTAX. All oe messages names are prefixed with "oe" . oe message names may be generic. oe messages must be modeled using continuous arrows and following this structure:

the participant -> system : oeMessage(parameters)

for example : alex -> system : oeConstructionRequest("hpc")

13. OUTPUT_STRUCTURE_STANDARDIZATION. All persona outputs and diagram elements must follow consistent structure guidelines:
    - Use camelCase for all field names, actor names, and message names
    - Use descriptive, consistent naming across all participants and personas
    - Maintain hierarchical structure where appropriate
    - Document any deviations from standard patterns
    - Follow unified error handling format with "reasoning_summary", "data", and "errors" fields
    - Ensure all required fields are present and properly typed

14. ACTIVATOR_BARS. Activator bars must never be nested. For each event, an activator bar must be defined that is always beginning just after a message and ends shortly before the next message. Activation bars must always be located on the side of the participant lifeline, never on the side of the System. Strictly following this order of definition : firstly the event, then secondly activate the participant, then thirdly deactive the participant. 

15. NO_ACTIVATION_BAR_ON_SYSTEM. There must be NO activation bar in the System lifeline. Never activate System.

16. SYSTEM_PARTICIPANT_COLOR. the system participant rectangle background must be #E8C28A

17. OTHER_PARTICIPANTS_COLOR. the other participants (non-system) rectangle background must be #FFF3B3

18. INPUT_EVENT_ACTIVATION_BAR_COLOR. the background of an activation bar following an input event must be #C0EBFD

19. OUTPUT_EVENT_ACTIVATION_BAR_COLOR. the background of an activation bar following an output event must be #274364

20. MSG_PARAMS_FLEX_QUOTING. Message parameters format may be of any type. Parameters must be comma-separated and surrounded by single-quote (') OR double-quote (") OR no quote at all. A mix of single-quote, double-quote, no quote IS allowed within a parameter list.

21. MSG_ENHANCED_PARAMS. Message parameters must be realistic, detailed, and contextually relevant to enhance diagram clarity and understanding. Parameters should:
    - Use concrete, believable values that reflect actual system behavior
    - Include all relevant information needed for the operation (user identification, action details, system state, response data)
    - Reflect domain-specific terminology and data types from the original model
    - Avoid generic placeholders in favor of meaningful, specific values
    - Be properly formatted for readability with consistent quoting and spacing
    - Include realistic names, numbers, and text that would occur in actual system operation

