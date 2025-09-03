patches-own [heat]

to setup
  clear-all
  ask patches [
    set heat random 212
    set pcolor scale-color red heat 0 212
  ]
  reset-ticks
end

to go
  diffuse heat 1
  ask patches [
    ;; warm up patches till they reach 212
    set heat (heat + 5) mod 212
    set pcolor scale-color red heat 0 212
  ]
  tick
end

to-report average-heat
  report mean [heat] of patches
end


; Copyright 1998 Uri Wilensky.
; See Info tab for full copyright and license.