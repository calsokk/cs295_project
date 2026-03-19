-- Union and intersection types
type StringOrNumber = string | number
type Named = {name: string}
type Aged = {age: number}
type Person = Named & Aged

-- Typeof
local x = 42
type X = typeof(x)

-- Function overload-style types
type Formatter = ((number) -> string) & ((string) -> string)

-- Optional types
type Config = {
    debug: boolean?,
    verbose: boolean?,
    level: number?,
}

-- Recursive types
type LinkedList<T> = {value: T, next: LinkedList<T>?}

local list: LinkedList<number> = {
    value = 1,
    next = {
        value = 2,
        next = {
            value = 3,
            next = nil
        }
    }
}

-- Type assertion
local val = 42 :: any
local str = val :: string

-- Export type
export type PublicType = {
    id: number,
    data: string,
}
