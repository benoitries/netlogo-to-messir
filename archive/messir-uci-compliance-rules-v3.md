# **Messir Use Case Instance Domain-Specific Modeling Language**

Messir is a scientific methodology covering the requirements, design, test and validation phases. It defines a set of Domain-Specific Modeling Languages based on UML and OCL.

## Messir Use-Case Instance Concepts

### **Messir Use-Case Instance Model (MUCIM)**
A structured model representing a single use-case scenario in Messir. It defines the interaction between the system and actors through input and output events, enriched with parameters and visualized using sequence diagrams. MUCIM serves as the core modeling unit for compliance, simulation, and documentation.

### **System (SYS)**
The central entity in the model that represents the software or organizational system. It is unique in each diagram and serves as the sender or receiver of events. It cannot activate itself or send messages to itself. In MUCIM, the System is the core reactive component.

### **Actors (ACT)**
External entities that interact with the system. Each actor represents a role or persona from the domain and can initiate or receive events. Actors cannot communicate directly with each other. In MUCIM, actors are modeled as participants with domain-specific roles.

### **Input Events (IE)**
Events sent **from the system to an actor**. They represent system-initiated events. Input events are prefixed with `ie` and use dashed arrows in the diagram. In MUCIM, input events reflect the system's responses or triggers toward actors.

### **Output Events (OE)**
Events sent **from an actor to the system**. They represent actor-initiated events. Output events are prefixed with `oe` and use solid arrows in the diagram. In MUCIM, output events represent external stimuli or commands directed at the system.

### **Event Parameters (EP)**
Data attached to events that describe the context, content, or intent of the interaction. Parameters must be realistic, domain-specific, and formatted for clarity. They can include identifiers, textual content, or structured values. In MUCIM, parameters enrich event semantics and support traceability.

### **Activation Bars (AB)**
Visual indicators of a participant's active period during an event. They are placed only on actors (never on the system) and follow strict ordering and color conventions based on the event type. In MUCIM, activation bars help visualize temporal engagement of actors.


## Well-Formedness Rules (WFR)

### **Abstract Syntax (AS)**

**AS_SYS**
AS_SYS_UNIQUE.
There must be exactly one System per model that is always named System

AS_SYS_DECLARED_FIRST.
The System must be declared first before all actors.

AS_SYS_ACT_ALLOWED_EVENTS.
Events must always be from System (resp. Actor) to an Actor (resp. the System) . System → Actor or Actor → System 

AS_SYS_NO_SELF_LOOP.
Events must never be from System to System . System → System

**AS_ACT**
AS_ACT_DECLARED_AFTER_SYS.
The actors must be declared after the System.

AS_ACT_NO_ACT_ACT_EVENTS.
Events must never be from Actor to Actor . Actor → Actor

AS_ACT_TYPE_FORMAT.
Actor type name must be human-readable, in FirstCapitalLetterFormat and prefixed by "Act"
Example 1 : ActMsrCreator
Example 2 : ActEcologist

**AS_IE**
AS_IE_EVENT_DIRECTION.
System sends event TO actor (System → Actor) - Input Event FROM System TO actor
Note. The "ie" prefix refers to the actor's perspective, not the system's perspective

**AS_OE**
AS_OE_EVENT_DIRECTION.
Actor sends event TO System (Actor → System) - Output Event FROM actor TO System
Note. The "oe" prefix refers to the actor's perspective, not the system's perspective

**AS_AB**
AS_AB_NO_NESTING.
Activator bars must never be nested.

AS_AB_ORDER.
For each event, an activator bar must be defined that is always beginning just after the event.
Activation bars must always be located on the side of the actor lifeline, never on the side of the System.
Strictly following this order of definition . (1) the event, (2) the activation bar on the lifeline of the actor related to the event 

AS_AB_NO_OVERLAPPING.
Activation bars must never overlap. following sequence is forbidden : an event, start of activation bar of this event, another event before the end of the activation bar.

### **Concrete Syntax (CS)**

**CS_MUCIM**
CS_MUCIM_REPRESENTATION.
A Messir use case instance **must be represented as a UML Sequence Diagram** using strictly plantUML textual syntax.

CS_MUCIM_ALLOW_BLANK_LINES.
In plantUML diagrams, blank lines are allowed and must safely be ignored.

**CS_SYS**
CS_SYS_DECLARATION.
System must be declared first before the actors and using the syntax : participant System as system

CS_SYS_PARTICIPANT_RECTANGLE.
System must be declared as a plantUML participant, with a rectangle shape.

CS_SYS_COLOR.
The System rectangle background must be #E8C28A

**CS_ACT**
CS_ACT_PARTICIPANT_RECTANGLE.
Each actor is modelled as a PlantUML participant with a rectangle-shape.

CS_ACT_DECLARATION_SYNTAX.
Each actor must be modelled using this plantUML syntax :
participant "theParticipantName:ActParticipantType" as theParticipantName
Example 1: participant "theCreator:ActMsrCreator" as theCreator
Example 2: participant "chris:ActEcologist" as chris

CS_ACT_NAMES.
All actor names must be human-readable, in camelCase and prefixed with "act".
Example: actAdministrator

CS_ACT_COLOR.
The actors rectangle background must be #FFF3B3

**CS_IE**
CS_IE_SYNTAX.
All ie event names are prefixed with "ie".
ie event names may be generic.
ie events must be modeled using dashed arrows and following this declaration syntax:
system --> theParticipant : ieMessageName(EP)
Example 1 : system --> jen : ieValidationFromTownHall()
Example 2 : system --> jen : ieMessage("Congratulations jen for your 6-years mandate as a major of the town !")

CS_AB_IE_COLOR.
The background of an activation bar placed just after an input event must be #C0EBFD

**CS_OE**
CS_OE_SYNTAX.
All oe event names are prefixed with "oe"
oe event names may be generic.
oe events must be modeled using continuous arrows and following this declaration syntax:
the participant -> system : oeMessage(EP)
Example: alex -> system : oeConstructionRequest("hpc")

**CS_EP**
CS_EP_TYPE.
Event parameters format may be of any type.

CS_EP_FLEX_QUOTING.
Each event parameter may be surrounded by single-quote (') OR double-quote (") OR no quote at all. A mix of single-quote, double-quote, no quote IS allowed within a parameter list.

CS_EP_COMMA_SEPARATED.
Multiple parameters must be comma-separated. 

**CS_AB**
CS_AB_SEQUENCE.
Strictly follow this sequence of instructions for activation bars declarations:
(1) an event declaration
(2) activate the participant related to the event
(3) deactive the participant related to the event

CS_AB_NO_ACTIVATION_BAR_ON_SYSTEM.
There must be NO activation bar in the System lifeline. Never activate System.

CS_AB_OE_COLOR.
The background of an activation bar placed just after an output event must be #274364
