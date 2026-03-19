local x = 10

if x > 5 then
    print("big")
elseif x > 0 then
    print("small")
else
    print("zero or negative")
end

for i = 1, 10 do
    x = x + i
end

for i = 10, 1, -1 do
    x = x - 1
end

while x > 0 do
    x = x - 1
end

repeat
    x = x + 1
until x > 5

do
    local temp = x * 2
    x = temp
end
