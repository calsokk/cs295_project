local t = {a = 1, b = "hello", [3] = true}

for k, v in pairs(t) do
    print(k, v)
end

local arr = {10, 20, 30, 40, 50}
for i, v in ipairs(arr) do
    print(i, v)
end

local nested = {
    inner = {1, 2, 3},
    meta = {name = "test"}
}
print(nested.inner[1])
print(nested.meta.name)

table.insert(arr, 60)
table.remove(arr, 1)
print(#arr)
