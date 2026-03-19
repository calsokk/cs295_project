type Point = {x: number, y: number}
type Callback = (number, string) -> boolean
type Optional<T> = T | nil
type StringMap = {[string]: number}

local p: Point = {x = 1, y = 2}
local f: Callback = function(n, s) return n > 0 end

local function identity<T>(x: T): T
    return x
end

local n = identity(42)
local s = identity("hello")

type Result<T, E> = {
    ok: boolean,
    value: T?,
    error: E?,
}
