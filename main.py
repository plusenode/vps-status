import discord, json
import paramiko
from discord.ext import tasks
import time, asyncio
bot = discord.Bot()

###############################################################################################################


app_name = "Server Status"
token = ""
guild_id = 1227332240027947039

active_tasks = {} # DONT CHANGE
message_ids = {} # DONT CHANGE


###############################################################################################################


def mean(first, second, zone):
    y = (second - first)
    if zone == 'US':
        y *= 8
    y = y / 1000 / 1000
    y = round(y, 2)
    return json.dumps([y])


###############################################################################################################


def data_fetch(typ, interface, ssh):
    command = f"cat /sys/class/net/{interface}/statistics/{typ}_bytes"
    stdin, stdout, stderr = ssh.exec_command(command)
    data1 = int(stdout.read().decode().strip())
    time.sleep(1)
    stdin, stdout, stderr = ssh.exec_command(command)
    data2 = int(stdout.read().decode().strip())
    return [data1, data2]


###############################################################################################################


@bot.event
async def on_ready():
    print(f"We have logged in as {bot.user}")
    await check_server_json()


###############################################################################################################


async def task_loop(name):
    # Scraping data from json
    with open("server.json", "r") as f:
        data = json.load(f)

    # Check if Server is enabled
    try:
        if data[name]["enabled"] == False:
            return
    except:
        pass

    # SSH Connection to the Server
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostname=data[name]["ip"], username=data[name]["credentials"]["username"], password=data[name]["credentials"]["password"])

        # RX for received
        rtx = data_fetch("rx", "eth0", ssh)
        incomm = mean(rtx[0], rtx[1], "US")

        # TX for transferred
        rtx = data_fetch("tx", "eth0", ssh)
        outcomm = mean(rtx[0], rtx[1], "US")

        # CPU Usage
        command = """top -bn1 | grep "Cpu(s)" | awk '{print $2+$4+$6"%"}'"""
        stdin, stdout, stderr = ssh.exec_command(command)
        data1 = stdout.read().decode().strip()

        # RAM Usage
        command = """cat /proc/meminfo | awk '/MemTotal/{total=$2} /MemAvailable/{available=$2} END {print (total - available)/1024/1024}'"""
        stdin, stdout, stderr = ssh.exec_command(command)
        ram = float(stdout.read().decode().strip())

        # Connection Count
        command = """netstat -at | grep "ESTABLISHED" | wc -l"""
        stdin, stdout, stderr = ssh.exec_command(command)
        connections = stdout.read().decode().strip()

        # Check if message already has been sent.
        if name in message_ids:
            channel = await bot.fetch_channel(data[name]["channel"])
            msg = await channel.fetch_message(message_ids[name])
            embed = discord.Embed(title=f"Status [{name}] | {app_name}", colour=discord.Colour(0x9803fc))
            embed.add_field(name="CPU Usage",value=f"``{data1}``", inline=True)
            embed.add_field(name="RAM Usage",value=f"``{round(ram, 2)} GB``", inline=True)
            embed.add_field(name="Active Connections",value=f"``{connections}``", inline=True)
            embed.add_field(name="Network Usage",value=f"> ```\n> Interface: eth0\n> IN:  {incomm} Mbps\n> OUT: {outcomm} Mbps\n> ```", inline=False)
            await msg.edit(embed=embed)
        else:
            channel = await bot.fetch_channel(data[name]["channel"])
            embed = discord.Embed(title=f"Status [{name}] | {app_name}", colour=discord.Colour(0x9803fc))
            embed.add_field(name="CPU Usage",value=f"``{data1}``", inline=True)
            embed.add_field(name="RAM Usage",value=f"``{round(ram, 2)} GB``", inline=True)
            embed.add_field(name="Active Connections",value=f"``{connections}``", inline=True)
            embed.add_field(name="Network Usage",value=f"> ```\n> Interface: eth0\n> IN:  {incomm} Mbps\n> OUT: {outcomm} Mbps\n> ```", inline=False)
            gg = await channel.send(embed=embed)
            message_ids[name] = gg.id
        ssh.close()
    except:
        print(f"Error on Server [{name}]")


###############################################################################################################



def task_generator(name):
    # Creating Task
    print(f"[+] Started [{name}]")
    t = tasks.loop(seconds=5)(task_loop)
    active_tasks[name] = t
    t.start(name)


###############################################################################################################


async def check_server_json():
    while True:
        with open("server.json", "r") as f:
            data = json.load(f)
        # Create new Task 
        for new_item in data.keys():
            if new_item not in active_tasks:
                task_generator(new_item)
        # if server gets removed task will closed
        for existing_task_name in list(active_tasks.keys()):
            if existing_task_name not in data:
                await stop_task(existing_task_name)
        await asyncio.sleep(10)


###############################################################################################################


async def stop_task(name):
    if name in active_tasks:
        print(f"[+] Stopping task for [{name}]")
        active_tasks[name].stop()
        del active_tasks[name]


###############################################################################################################


@bot.slash_command(guild_ids=[guild_id])
async def servers(ctx):
    with open("server.json", "r") as f:
        data = json.load(f)
    server = "> ```css"
    max_length = max(len(x) for x in data.keys())
    for x in data.keys():
        spaces = " " * (max_length - len(x))
        server += f"\n> {x}{spaces} » {data[x]['ip']}:{data[x]['port']} {'🟢' if data[x]['enabled'] else '🔴'}"
    server += "\n> ```"
    embed = discord.Embed(title=f"Servers | {app_name}", colour=discord.Colour(0x9803fc))
    embed.add_field(name="Server(s)",value=server, inline=False)
    await ctx.respond(embed=embed, ephemeral=True)


###############################################################################################################


bot.run(token)