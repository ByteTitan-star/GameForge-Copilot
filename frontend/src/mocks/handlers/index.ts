import { adminHandlers } from './admin'
import { authHandlers } from './auth'
import { gamesHandlers } from './games'
import { meHandlers } from './me'

export const handlers = [...authHandlers, ...meHandlers, ...gamesHandlers, ...adminHandlers]
