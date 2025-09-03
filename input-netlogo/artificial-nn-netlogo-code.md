links-own [ weight ]

breed [ bias-nodes bias-node ]
breed [ input-nodes input-node ]
breed [ output-nodes output-node ]
breed [ hidden-nodes hidden-node ]

turtles-own [
  activation     ;; Determines the nodes output
  err            ;; Used by backpropagation to feed error backwards
]

globals [
  epoch-error    ;; measurement of how many training examples the network got wrong in the epoch
  input-node-1   ;; keep the input and output nodes
  input-node-2   ;; in global variables so we can
  output-node-1  ;; refer to them directly
]

;;;
;;; SETUP PROCEDURES
;;;

to setup
  clear-all
  ask patches [ set pcolor gray ]
  set-default-shape bias-nodes "bias-node"
  set-default-shape input-nodes "circle"
  set-default-shape output-nodes "output-node"
  set-default-shape hidden-nodes "output-node"
  set-default-shape links "small-arrow-shape"
  setup-nodes
  setup-links
  propagate
  reset-ticks
end

to setup-nodes
  create-bias-nodes 1 [ setxy -4 6 ]
  ask bias-nodes [ set activation 1 ]
  create-input-nodes 1 [
    setxy -6 -2
    set input-node-1 self
  ]
  create-input-nodes 1 [
    setxy -6 2
    set input-node-2 self
  ]
  ask input-nodes [ set activation random 2 ]
  create-hidden-nodes 1 [ setxy 0 -2 ]
  create-hidden-nodes 1 [ setxy 0  2 ]
  ask hidden-nodes [
    set activation random 2
    set size 1.5
  ]
  create-output-nodes 1 [
    setxy 5 0
    set output-node-1 self
    set activation random 2
  ]
end

to setup-links
  connect-all bias-nodes hidden-nodes
  connect-all bias-nodes output-nodes
  connect-all input-nodes hidden-nodes
  connect-all hidden-nodes output-nodes
end

to connect-all [ nodes1 nodes2 ]
  ask nodes1 [
    create-links-to nodes2 [
      set weight random-float 0.2 - 0.1
    ]
  ]
end

to recolor
  ask turtles [
    set color item (step activation) [ black white ]
  ]
  ask links [
    set thickness 0.05 * abs weight
    ifelse show-weights? [
      set label precision weight 4
    ] [
      set label ""
    ]
    ifelse weight > 0
      [ set color [ 255 0 0 196 ] ] ; transparent red
      [ set color [ 0 0 255 196 ] ] ; transparent light blue
  ]
end

;;;
;;; TRAINING PROCEDURES
;;;

to train
  set epoch-error 0
  repeat examples-per-epoch [
    ask input-nodes [ set activation random 2 ]
    propagate
    backpropagate
  ]
  set epoch-error epoch-error / examples-per-epoch
  tick
end

;;;
;;; FUNCTIONS TO LEARN
;;;

to-report target-answer
  let a [ activation ] of input-node-1 = 1
  let b [ activation ] of input-node-2 = 1
  ;; run-result will interpret target-function as the appropriate boolean operator
  report ifelse-value run-result
    (word "a " target-function " b") [ 1 ] [ 0 ]
end

;;;
;;; PROPAGATION PROCEDURES
;;;

;; carry out one calculation from beginning to end
to propagate
  ask hidden-nodes [ set activation new-activation ]
  ask output-nodes [ set activation new-activation ]
  recolor
end

;; Determine the activation of a node based on the activation of its input nodes
to-report new-activation  ;; node procedure
  report sigmoid sum [ [ activation ] of end1 * weight ] of my-in-links
end

;; changes weights to correct for errors
to backpropagate
  let example-error 0
  let answer target-answer

  ask output-node-1 [
    ;; `activation * (1 - activation)` is used because it is the
    ;; derivative of the sigmoid activation function. If we used a
    ;; different activation function, we would use its derivative.
    set err activation * (1 - activation) * (answer - activation)
    set example-error example-error + ((answer - activation) ^ 2)
  ]
  set epoch-error epoch-error + example-error

  ;; The hidden layer nodes are given error values adjusted appropriately for their
  ;; link weights
  ask hidden-nodes [
    set err activation * (1 - activation) * sum [ weight * [ err ] of end2 ] of my-out-links
  ]
  ask links [
    set weight weight + learning-rate * [ err ] of end2 * [ activation ] of end1
  ]
end

;;;
;;; MISC PROCEDURES
;;;

;; computes the sigmoid function given an input value and the weight on the link
to-report sigmoid [input]
  report 1 / (1 + e ^ (- input))
end

;; computes the step function given an input value and the weight on the link
to-report step [input]
  report ifelse-value input > 0.5 [ 1 ] [ 0 ]
end

;;;
;;; TESTING PROCEDURES
;;;

;; test runs one instance and computes the output
to test
  let result result-for-inputs input-1 input-2
  let correct? ifelse-value result = target-answer [ "correct" ] [ "incorrect" ]
  user-message (word
    "The expected answer for " input-1 " " target-function " " input-2 " is " target-answer ".\n\n"
    "The network reported " result ", which is " correct? ".")
end

to-report result-for-inputs [n1 n2]
  ask input-node-1 [ set activation n1 ]
  ask input-node-2 [ set activation n2 ]
  propagate
  report step [ activation ] of one-of output-nodes
end


; Copyright 2006 Uri Wilensky.
; See Info tab for full copyright and license.