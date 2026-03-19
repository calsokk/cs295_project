type Array<T> = {T}
type Map<K, V> = {[K]: V}
type Pair<A, B> = {first: A, second: B}

local nums: Array<number> = {1, 2, 3}
local names: Map<string, number> = {alice = 1, bob = 2}

local function first<T>(arr: Array<T>): T?
    return arr[1]
end

local function map<T, U>(arr: Array<T>, f: (T) -> U): Array<U>
    local result: Array<U> = {}
    for _, v in ipairs(arr) do
        table.insert(result, f(v))
    end
    return result
end

local doubled = map(nums, function(x) return x * 2 end)
print(first(doubled))
