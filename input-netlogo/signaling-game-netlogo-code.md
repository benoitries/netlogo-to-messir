globals [
  sender      ; the player perceiving a world state and sending a signal
  receiver    ; the player perceiving a signal and guessing the state
  world-state ; the currently active world state
]

; There are two players: a sender and a receiver.
breed [ players player ]

; States represent the possible states that the world can be in.
; Only one of them is active on each tick.
breed [ states state ]

; Signals represent possible signals that the sender can use
; to try to communicate the observed world state to the receiver.
breed [ signals signal ]

; Observations link a world state to the sender that's perceiving it
; or a signal to the receiver that's perceiving it.
directed-link-breed [ observations observation ]

; Choices link the sender to the world state that the sender thinks
; the receiver meant by the chosen signal.
directed-link-breed [ choices choice ]

; Urns are used to represent the associations between states and signals in the
; minds of the players:
;
; - The sender has an urn for each possible world state, and each ball in the urn
;   is a signal that the sender can use to represent that state. When the sender
;   observes a state, the sender picks a "signal ball" in the corresponding "state
;   urn" and sends that signal to the receiver.
; - The receiver has an urn for each possible signal. When the receiver sees a
;   signal, the receiver picks a ball in the corresponding "signal urn": each
;   ball is a state that the receiver can interpret the signal to mean.
;
; When communication is successful, the sender puts another copy of the "signal ball"
; in the "state urn" and the receiver puts another copy of the "state ball" in the
; "signal urn", increasing the probability that this state is associated with this
; signal in the future.
undirected-link-breed [ urns urn ]
urns-own [ balls ]

to setup
  clear-all
  ask patches [ set pcolor black + 1 ]
  setup-states
  setup-signals
  setup-players
  reset-ticks
end

to go
  if probability-of-success > 0.99 [ stop ]
  ; prepare the world for this round
  ask choices [ die ]
  ask observations [ die ]
  ask states [ look-inactive ]
  ask signals [ look-inactive ]
  ask players [ set shape "face neutral" ]
  set world-state one-of states
  ask world-state [ look-active ]

  ; the sender chooses a signal in response to the world state
  ask sender [
    observe world-state
    pick-from urn-with world-state
  ]
  ask chosen-signal [ look-active ]

  ; the receiver chooses the world state to act on, in response to the signal
  ask receiver [
    observe chosen-signal
    pick-from urn-with chosen-signal
  ]

  ifelse (guessed-state = world-state) [
    ; when the choice is correct, both players are happy
    ask [ my-out-choices ] of receiver [ set color lime ]
    ask players [ set shape "face happy" ]
    ; and the probability of choosing the same signal and actions
    ; is increased by adding the successful choices as balls in the players urns:
    ask [ urn-with world-state ] of sender [ set balls lput chosen-signal balls ]
    ask [ urn-with chosen-signal ] of receiver [ set balls lput guessed-state balls ]
  ]
  [ ; when the choice is wrong, both players are sad
    ask [ my-out-choices ] of receiver [ set color red ]
    ask players [ set shape "face sad" ]
  ]

  if print-probabilities? [ print-probabilities ]
  tick
end

to setup-states
  set-default-shape states "circle 2"
  foreach state-labels number-of-states [ the-label ->
    create-states 1 [
      set label the-label
      set color sky
      look-inactive
    ]
  ]
  spread-x (max-pycor - (world-height / 6)) states
  create-turtles 1 [ setxy 4.75 max-pycor - 2 set label "world states" set size 0 set label-color grey ]
end

to setup-signals
  set-default-shape signals "square 2"
  foreach signal-labels number-of-signals [ the-label ->
    create-signals 1 [
      set label the-label
      set color magenta
      look-inactive
    ]
  ]
  spread-x (min-pycor + (world-height / 6)) signals
  create-turtles 1 [
    setxy 2.75 min-pycor + 1
    set label "signals"
    set size 0
    set label-color grey
  ]
end

to setup-players
  set-default-shape players "face neutral"
  set-default-shape urns "empty"
  create-players 1 [
    set label "sender       "
    set sender self
    create-urns-with states [
      ; each possible world state is associated with an urn from which
      ; the sender picks signals, with equal probability at first
      set balls sort signals
    ]
  ]
  create-players 1 [
    set label "receiver       "
    set receiver self
    create-urns-with signals [
      ; each possible signal is associated with an urn from which
      ; the receiver picks states, with equal probability at first
      set balls sort states
    ]
  ]
  ask players [
    set size 3
    set color yellow
  ]
  spread-x 0 players
end

to observe [ thing ] ; player procedure
  create-observation-from thing [
    set color black + 2
  ]
  display
end

to pick-from [ this-urn ] ; player procedure
  create-choice-to [ one-of balls ] of this-urn [
    set thickness 0.3
    set color white
  ]
  display
end

to look-active ; states and signals procedure
  set color color + 3
  set label-color white
  set size size + 1
  set shape remove " 2" shape
end

to look-inactive ; states and signals procedure
  set size 2
  set color (base-shade-of color) - 3
  set label-color (base-shade-of color) + 3
  set shape word (remove " 2" shape) (" 2")
end

to spread-x [ y agents ] ; observer procedure
  let d world-width / (count agents + 1)
  let xs n-values count agents [ n -> (min-pxcor - 0.5) + d + (d * n) ]
  (foreach sort agents xs [ [a x] -> ask a [ setxy x y ] ])
end

to-report state-labels [ n ]
  report sublist ["A" "B" "C" "D" "E" "F" "G" "H"] 0 n
end

to-report signal-labels [ n ]
  report n-values n [ the-label -> the-label ]
end

to-report base-shade-of [ some-color ]
  report some-color - (some-color mod 10) + 5
end

to-report chosen-signal
  report [ one-of out-choice-neighbors ] of sender
end

to-report guessed-state
  report [ one-of out-choice-neighbors ] of receiver
end

to-report times-correct
  report [ sum [ length balls - count signals ] of my-urns ] of sender
end

to-report times-wrong
  report ticks - times-correct
end

to print-probabilities
  clear-output
  output-print "Sender probabilities:"
  output-print probability-table states signals sender
  output-print ""
  output-print "Receiver probabilities:"
  output-print probability-table signals states receiver
end

to-report probability-table [ ys xs this-player ]
  let columns-labels fput "" map [ x -> [ label ] of x ] sort xs
  let separators fput "" n-values count xs [ "---" ]
  let rows map [ y -> [ make-row urn-with y ] of this-player ] sort ys
  let formatted-rows map format-list (fput columns-labels fput separators rows)
  report reduce [ [a b] -> (word a "\n" b) ] formatted-rows
end

to-report make-row [ this-urn ]
  let header-column word ([ label ] of [ end1 ] of this-urn) " :"
  let other-columns map [ p -> p * 100 ] probabilities this-urn
  report fput header-column other-columns
end

to-report format-list [ this-list ]
  let formatted-values map [ value -> format-value value 4 ] this-list
  report reduce [ [a b] -> (word a "  " b) ] formatted-values
end

to-report format-value [ x width ]
  let str (word ifelse-value is-number? x [ precision x 0 ] [ x ])
  let padding ifelse-value length str < width
    [ reduce word (n-values (width - length str) [ " " ]) ]
    [ "" ]
  report word padding str
end

to-report probabilities [ this-urn ]
  let this-breed [ breed ] of first [ balls ] of this-urn
  report normalize map [ a -> instances a [ balls ] of this-urn ] sort this-breed
end

to-report instances [ x this-list ]
  ; report the number of instances of x in this-list
  report reduce [ [a b] -> a + ifelse-value b = x [ 1 ] [ 0 ] ] fput 0 this-list
end

to-report normalize [ this-list ]
  let total sum this-list
  report map [ n -> n / total ] this-list
end

to-report probability-of-success
  report (sum [ probability-of-state-success ] of states) / count states
end

to-report probability-of-state-success ; state reporter
  let target-state self
  let this-urn [ urn-with target-state ] of sender
  report sum [
    [ probability-of-choosing myself ] of this-urn * probability-of-signal-success target-state
  ] of signals
end

to-report probability-of-signal-success [ target-state ] ; signal reporter
  let this-urn [ urn-with myself ] of receiver
  report [ probability-of-choosing target-state ] of this-urn
end

to-report probability-of-choosing [ target ] ; urn reporter
  report (instances target balls) / (length balls)
end


; Copyright 2016 Uri Wilensky.
; See Info tab for full copyright and license.