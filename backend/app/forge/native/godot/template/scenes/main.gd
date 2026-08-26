extends Node2D

const READY_SIGNAL := "GAMEFORGE_READY"

func _ready() -> void:
	print(READY_SIGNAL)
