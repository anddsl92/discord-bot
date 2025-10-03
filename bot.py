import os
import discord
import json
import asyncio
import aiohttp
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load biến môi trường từ file .env
load_dotenv()

# Cấu hình bot
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Database đơn giản (lưu trong bộ nhớ)
auctions_db = {}
checkins_db = {}
active_threads = {}
user_sessions = {}
countdown_messages = {}  # Lưu tin nhắn đếm ngược theo thread
user_roles_db = {}  # Lưu thông tin role của user
set_role_threads = {}  # Lưu thread set role theo server
pending_boss_approvals = {}  # Lưu tạm boss chờ duyệt

# ===============================
# CẤU HÌNH - ĐÃ ĐIỀU CHỈNH CHO RENDER & WEBHOOK.SITE
# ===============================
BOT_NICKNAME = "Bot"  # Nickname bạn muốn hiển thị
SET_ROLE_CHANNEL_NAME = "role"  # Tên kênh set role
CHAMCONG_CHANNEL_NAME = "chấm-công-boss-không-chạm"  # Tên kênh chấm công đã đổi

# WEBHOOK.SITE URL - THAY THẾ BẰNG URL CỦA BẠN
WEBHOOK_URL = os.getenv('WEBHOOK_URL', 'https://webhook.site/0669e4d2-1d6a-40b9-af5f-27b7d79218c6')

# Role options cho hệ thống Set Role với VIẾT TẮT cho nickname
ROLE_OPTIONS = [
    {"name": "Kiếm Sĩ", "value": "KS", "full_name": "Kiếm Sĩ", "short_code": "KS"},
    {"name": "Song Kiếm", "value": "SK", "full_name": "Song Kiếm", "short_code": "SK"},
    {"name": "Dao Găm", "value": "DG", "full_name": "Dao Găm", "short_code": "DG"},
    {"name": "Giáo", "value": "GI", "full_name": "Giáo", "short_code": "GI"},
    {"name": "Cung", "value": "CG", "full_name": "Cung", "short_code": "CG"},
    {"name": "Cầu Phép", "value": "CP", "full_name": "Cầu Phép", "short_code": "CP"},
    {"name": "Trượng", "value": "TG", "full_name": "Trượng", "short_code": "TG"}
]

GUILD_OPTIONS = [
    {"name": "AEVN", "value": "AEVN"},
    {"name": "Warrior", "value": "Warrior"},
    {"name": "Minas", "value": "Minas"}
]

GUILD_ROLE_OPTIONS = [
    {"name": "Thành Viên", "value": "TV", "emoji": ""},
    {"name": "Bảo Vệ", "value": "BV", "emoji": "🛡️"},
    {"name": "Quân Chủ", "value": "QC", "emoji": "👑"}
]

BOSS_LIST = [
    {"name": "Orfen", "value": "orfen"},
    {"name": "Orfen Xâm Lược", "value": "orfen_xam_luoc"},
    {"name": "Silla", "value": "silla"},
    {"name": "Murf", "value": "murf"},
    {"name": "Normus", "value": "normus"},
    {"name": "Ukanba", "value": "ukanba"},
    {"name": "Selihorden", "value": "selihorden"}
]

VI_TRI_OPTIONS = [
    {"name": "Buff+Khiên", "value": "buff_khien"},
    {"name": "Hồi Máu Đơn", "value": "hoi_mau_don"}
]

# Biến toàn cục cho ảnh boss - sẽ được khởi tạo sau
BOSS_IMAGES = {}

# ===============================
# HÀM HỖ TRỢ SET ROLE
# ===============================

async def assign_chamcong_permissions(member: discord.Member, guild: discord.Guild):
    """Cấp quyền truy cập kênh chấm công cho thành viên"""
    try:
        # Tìm kênh chấm công
        chamcong_channel = discord.utils.get(guild.text_channels, name=CHAMCONG_CHANNEL_NAME)
        
        if chamcong_channel:
            # Cấp quyền xem và gửi tin nhắn trong kênh chấm công
            await chamcong_channel.set_permissions(member, 
                                                read_messages=True, 
                                                send_messages=True,
                                                view_channel=True)
            print(f"✅ Đã cấp quyền chấm công cho {member.name}")
        else:
            print(f"⚠️ Không tìm thấy kênh {CHAMCONG_CHANNEL_NAME}")
            
    except Exception as e:
        print(f"⚠️ Không thể cấp quyền chấm công cho {member.name}: {e}")

async def change_user_nickname(user: discord.Member, new_nickname: str) -> bool:
    """
    Cố gắng đổi nickname cho user
    Trả về True nếu thành công, False nếu thất bại
    """
    try:
        # Kiểm tra xem user có phải là chủ server không
        if user == user.guild.owner:
            print(f"⚠️ Không thể đổi nickname cho chủ server: {user.name}")
            return False
            
        # Kiểm tra quyền của bot
        if not user.guild.me.guild_permissions.manage_nicknames:
            print(f"⚠️ Bot không có quyền Manage Nicknames trong server: {user.guild.name}")
            return False
            
        # Kiểm tra vị trí role - bot cần có role cao hơn user
        if user.guild.me.top_role <= user.top_role and user != user.guild.owner:
            print(f"⚠️ Role của bot không đủ cao để đổi nickname cho: {user.name}")
            return False
            
        await user.edit(nick=new_nickname)
        print(f"✅ Đã đổi nickname thành công cho {user.name}")
        return True
        
    except discord.Forbidden:
        print(f"❌ Không có quyền đổi nickname cho {user.name}")
        return False
    except discord.HTTPException as e:
        print(f"❌ Lỗi khi đổi nickname cho {user.name}: {e}")
        return False

def process_character_name(name: str) -> str:
    """Xử lý tên nhân vật: thay 'I' thành 'l' và rút gọn LineAge"""
    # Thay thế 'I' thành 'l'
    name = name.replace('I', 'l')
    
    # Xử lý rút gọn cho tên bắt đầu bằng LineAge
    if name.startswith('LineAge') and len(name) > 11:  # LineAge + ít nhất 4 ký tự
        # Giữ 7 ký tự đầu (LineAge) và 4 ký tự cuối, phần giữa thay bằng ..
        processed_name = name[:7] + '..' + name[-4:]
        return processed_name
    
    return name

def create_nickname(tên: str, role_short: str, character_name: str, guild: str, guild_role_emoji: str) -> str:
    """Tạo nickname theo định dạng: Tên-RoleShort-CharacterName-GuildEmoji"""
    # Xử lý tên nhân vật
    processed_name = process_character_name(character_name)
    
    # Tạo nickname
    nickname = f"{tên}-{role_short}-{processed_name}-{guild}{guild_role_emoji}"
    
    # Kiểm tra và cắt bớt nếu vượt quá 32 ký tự (giới hạn của Discord)
    if len(nickname) > 32:
        # Tính toán phần cố định
        fixed_part = f"{tên}-{role_short}-{guild}{guild_role_emoji}"
        fixed_length = len(fixed_part) + 1  # +1 cho dấu gạch nối cuối cùng
        
        # Tính số ký tự còn lại cho tên nhân vật
        max_name_length = 32 - fixed_length
        
        if max_name_length > 0:
            # Cắt bớt tên nhân vật
            processed_name = processed_name[:max_name_length]
            nickname = f"{tên}-{role_short}-{processed_name}-{guild}{guild_role_emoji}"
        else:
            # Nếu phần cố định đã quá dài, chỉ giữ phần cố định (bỏ tên nhân vật)
            nickname = fixed_part
    
    return nickname

async def send_to_webhook(data: dict):
    """Gửi dữ liệu đến webhook.site - ĐÃ ĐIỀU CHỈNH"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(WEBHOOK_URL, json=data) as response:
                if response.status == 200:
                    print(f"✅ Đã gửi dữ liệu đến webhook: {data}")
                    return True
                else:
                    print(f"❌ Lỗi khi gửi đến webhook: {response.status}")
                    return False
    except Exception as e:
        print(f"❌ Không thể kết nối đến webhook: {e}")
        return False

def load_boss_images():
    """Đọc ảnh boss từ file anhboss.txt"""
    boss_images = {}
    try:
        if os.path.exists('anhboss.txt'):
            with open('anhboss.txt', 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and '=' in line:
                        boss_name, image_url = line.split('=', 1)
                        boss_images[boss_name.strip()] = image_url.strip()
            print(f"✅ Đã tải {len(boss_images)} ảnh boss từ file")
        else:
            print("⚠️ Không tìm thấy file anhboss.txt")
    except Exception as e:
        print(f"❌ Lỗi khi đọc file anhboss.txt: {e}")
    return boss_images

# ===============================
# TASK KIỂM TRA AUCTION HẾT HẠN
# ===============================

@tasks.loop(seconds=10)
async def check_auction_expiry():
    """Kiểm tra auction hết hạn và hiển thị đếm ngược - SỬ DỤNG DISCORD TIME"""
    current_time = discord.utils.utcnow()
    expired_auctions = []
    
    for auction_id, auction in auctions_db.items():
        if auction.get('ended', False):
            continue
            
        thread_id = auction.get('thread_id')
        if not thread_id:
            continue
            
        try:
            thread = bot.get_channel(thread_id)
            if not thread:
                continue
                
            time_remaining = auction['end_time'] - current_time
            total_seconds = time_remaining.total_seconds()
            
            # KIỂM TRA NẾU ĐÃ HẾT HẠN
            if total_seconds <= 0:
                expired_auctions.append(auction_id)
                auction['ended'] = True
                
                # Xóa tin nhắn đếm ngược cũ nếu có
                if thread_id in countdown_messages:
                    try:
                        old_msg = await thread.fetch_message(countdown_messages[thread_id])
                        await old_msg.delete()
                    except:
                        pass
                    del countdown_messages[thread_id]
                
                # KHOÁ THREAD TRƯỚC KHI CÔNG BỐ KẾT QUẢ
                await thread.edit(locked=True, archived=True)
                
                # XÁC ĐỊNH NGƯỜI THẮNG CUỘC (GỬI TRONG THREAD ĐÃ KHOÁ)
                if auction.get('last_bidder'):
                    winner = bot.get_user(auction['last_bidder'])
                    if winner:
                        # Sử dụng name thay vì mention
                        winner_name = winner.name
                        await thread.send(f"🎉 **NGƯỜI THẮNG CUỘC: 🏆 {winner_name} 🏆 VỚI GIÁ {auction['current_price']:,} 💎**")
                    else:
                        await thread.send(f"🎉 **NGƯỜI THẮNG CUỘC: <@{auction['last_bidder']}> VỚI GIÁ {auction['current_price']:,} 💎!**")
                else:
                    await thread.send("❌ **KHÔNG CÓ AI ĐẤU GIÁ!**")
                
                await thread.send("🛑 **PHIÊN ĐẤU GIÁ ĐÃ KẾT THÚC!**")
                continue
                
            # HIỂN THỊ ĐẾM NGƯỢC KHI VÀO 5 PHÚT CUỐI
            if 0 < total_seconds <= 300:  # 5 phút cuối = 300 giây
                minutes_remaining = int(total_seconds // 60)
                seconds_remaining = int(total_seconds % 60)
                
                # Chỉ cập nhật mỗi 30 giây hoặc khi có thay đổi quan trọng
                should_update = (
                    thread_id not in countdown_messages or
                    minutes_remaining == 0 or
                    seconds_remaining <= 10 or
                    total_seconds % 30 == 0
                )
                
                if should_update:
                    countdown_text = f"⏰ **THỜI GIAN CÒN LẠI: {minutes_remaining} phút {seconds_remaining} giây**"
                    
                    if thread_id in countdown_messages:
                        try:
                            # Cập nhật tin nhắn đếm ngược hiện tại
                            old_msg = await thread.fetch_message(countdown_messages[thread_id])
                            await old_msg.edit(content=countdown_text)
                        except:
                            # Nếu không tìm thấy tin nhắn cũ, tạo tin nhắn mới
                            new_msg = await thread.send(countdown_text)
                            countdown_messages[thread_id] = new_msg.id
                    else:
                        # Tạo tin nhắn đếm ngược mới
                        new_msg = await thread.send(countdown_text)
                        countdown_messages[thread_id] = new_msg.id
            else:
                # NẾU RA KHỎI 5 PHÚT CUỐI, XÓA TIN NHẮN ĐẾM NGƯỢC NẾU CÓ
                if thread_id in countdown_messages:
                    try:
                        old_msg = await thread.fetch_message(countdown_messages[thread_id])
                        await old_msg.delete()
                    except:
                        pass
                    del countdown_messages[thread_id]
                        
        except Exception as e:
            print(f"Lỗi khi kiểm tra auction {auction_id}: {e}")
    
    # Xóa auction đã hết hạn khỏi database
    for auction_id in expired_auctions:
        if auction_id in auctions_db:
            del auctions_db[auction_id]

# ===============================
# ĐỌC DỮ LIỆU VẬT PHẨM TỪ FILE
# ===============================

def load_auction_items():
    """Đọc danh sách vật phẩm từ file với emoji và phân loại"""
    items = []
    image_mapping = {}
    
    # Mapping mã màu sang emoji
    emoji_mapping = {
        'r': '🟥',  # Đỏ
        'p': '🟪',  # Tím
        'b': '🟦'   # Xanh
    }
    
    try:
        # Đọc file list_vat_pham.txt với mã màu và phân loại
        if os.path.exists('list_vat_pham.txt'):
            with open('list_vat_pham.txt', 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and '=' in line:
                        parts = line.split('=')
                        if len(parts) >= 3:
                            item_name = parts[0].strip()
                            item_category = parts[1].strip().lower()  # Phân loại (trượng, giáp, etc.)
                            color_code = parts[2].strip().lower()
                            
                            # Tạo giá trị duy nhất từ tên
                            item_value = item_name.lower().replace(' ', '_').replace('đ', 'd')
                            
                            # Xác định emoji dựa trên mã màu
                            item_emoji = emoji_mapping.get(color_code, '⚪')
                            
                            items.append({
                                "name": item_name,
                                "value": item_value,
                                "category": item_category,  # Thêm trường phân loại
                                "emoji": item_emoji,
                                "image_url": None,
                                "color_code": color_code
                            })
        
        # Đọc file anh_vat_pham.txt
        if os.path.exists('anh_vat_pham.txt'):
            with open('anh_vat_pham.txt', 'r', encoding='utf-8') as f:
                for line in f:
                    if '=' in line:
                        item_name, image_url = line.strip().split('=', 1)
                        image_mapping[item_name.strip()] = image_url.strip()
        
        # Kết hợp ảnh vào items
        for item in items:
            if item["name"] in image_mapping:
                image_url = image_mapping[item["name"]]
                if 'media.discordapp.net' in image_url:
                    image_url = image_url.replace('media.discordapp.net', 'cdn.discordapp.com')
                item["image_url"] = image_url
        
        print(f"✅ Đã tải {len(items)} vật phẩm từ file")
        return items
        
    except Exception as e:
        print(f"❌ Lỗi khi đọc file vật phẩm: {e}")
        return [
            {
                "name": "Vũ Khí Huyền Thoại", 
                "value": "legendary_weapon", 
                "category": "vũ_khí",
                "emoji": '🟪',
                "image_url": None,
                "color_code": "p"
            }
        ]

# Tải danh sách vật phẩm
AUCTION_ITEMS = load_auction_items()

# ===============================
# SỰ KIỆN BOT
# ===============================

@bot.event
async def on_ready():
    print(f'🎯 Bot {bot.user} đã đăng nhập thành công!')
    print(f'📊 Đang kết nối đến {len(bot.guilds)} server')
    
    # Khởi tạo BOSS_IMAGES sau khi bot ready
    global BOSS_IMAGES
    BOSS_IMAGES = load_boss_images()
    
    for guild in bot.guilds:
        print(f'   - {guild.name} (ID: {guild.id})')
    
    await change_nickname_in_all_servers()
    await setup_set_role_channel()
    
    try:
        synced = await bot.tree.sync()
        print(f'✅ Đã đồng bộ {len(synced)} slash commands')
        for cmd in synced:
            print(f'   - /{cmd.name}')
    except Exception as e:
        print(f'❌ Lỗi đồng bộ commands: {e}')
    
    check_auction_expiry.start()

async def change_nickname_in_all_servers():
    """Đổi nickname bot trong tất cả server"""
    for guild in bot.guilds:
        try:
            current_nick = guild.me.nick
            if current_nick != BOT_NICKNAME:
                await guild.me.edit(nick=BOT_NICKNAME)
                print(f'✅ Đã đổi nickname thành "{BOT_NICKNAME}" trong server: {guild.name}')
        except Exception as e:
            print(f'⚠️ Lỗi khi đổi nickname trong {guild.name}: {e}')

async def setup_set_role_channel():
    """Thiết lập kênh Set Role trong tất cả server"""
    for guild in bot.guilds:
        try:
            # Tìm kênh role nếu đã tồn tại
            set_role_channel = discord.utils.get(guild.text_channels, name=SET_ROLE_CHANNEL_NAME)
            
            if not set_role_channel:
                # Tạo kênh mới nếu chưa có
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(
                        send_messages=False,
                        read_messages=True,
                        create_public_threads=True,
                        send_messages_in_threads=True
                    ),
                    guild.me: discord.PermissionOverwrite(
                        send_messages=True,
                        read_messages=True,
                        manage_messages=True,
                        manage_channels=True,
                        manage_threads=True
                    )
                }
                
                set_role_channel = await guild.create_text_channel(
                    SET_ROLE_CHANNEL_NAME,
                    overwrites=overwrites,
                    reason="Tạo kênh Set Role cho thành viên đăng ký"
                )
                print(f'✅ Đã tạo kênh Set Role trong server: {guild.name}')
            
            # Kiểm tra và tái sử dụng chủ đề đăng ký role nếu đã tồn tại
            thread_name = "đăng-ký-role"
            thread = None
            
            # Tìm thread đang active
            for th in set_role_channel.threads:
                if th.name == thread_name:
                    thread = th
                    break
            
            # Nếu không tìm thấy, tìm trong archived threads
            if not thread:
                try:
                    async for th in set_role_channel.archived_threads(limit=100):
                        if th.name == thread_name:
                            thread = th
                            # Unarchive thread
                            await thread.edit(archived=False)
                            break
                except Exception as e:
                    print(f'⚠️ Không thể truy cập archived threads trong {guild.name}: {e}')
            
            # Nếu vẫn không tìm thấy, tạo thread mới
            if not thread:
                try:
                    # Tạo thread trực tiếp
                    thread = await set_role_channel.create_thread(
                        name=thread_name,
                        type=discord.ChannelType.public_thread,
                        reason="Tạo chủ đề đăng ký role cho thành viên"
                    )
                    print(f'✅ Đã tạo chủ đề đăng ký role mới trong server: {guild.name}')
                except Exception as e:
                    print(f'❌ Lỗi khi tạo thread trực tiếp trong {guild.name}: {e}')
                    continue
            else:
                print(f'✅ Đã tìm thấy chủ đề đăng ký role hiện có trong server: {guild.name}')
            
            # Lưu thread vào database
            set_role_threads[guild.id] = thread.id
                
        except Exception as e:
            print(f'⚠️ Lỗi khi thiết lập kênh Set Role trong {guild.name}: {e}')

@bot.event
async def on_guild_join(guild):
    """Khi bot được thêm vào server mới"""
    print(f'🎉 Bot đã được thêm vào server: {guild.name}')
    try:
        await guild.me.edit(nick=BOT_NICKNAME)
        print(f'✅ Đã đổi nickname thành "{BOT_NICKNAME}" trong server mới: {guild.name}')
        
        # Thiết lập kênh Set Role trong server mới
        await setup_set_role_channel()
        
    except Exception as e:
        print(f'⚠️ Không thể đổi nickname trong server mới {guild.name}: {e}')

# ===============================
# HỆ THỐNG SET ROLE MỚI VỚI 5 MỤC
# ===============================

@bot.tree.command(name="setrole", description="Đăng ký role và thiết lập tên nhân vật")
@app_commands.describe(
    tên="Tên của bạn (tối đa 10 ký tự)",
    role="Chọn role của bạn",
    tên_nhân_vật="Tên nhân vật trong game",
    guild="Chọn guild của bạn",
    vai_trò_guild="Chọn vai trò trong guild"
)
@app_commands.choices(role=[
    app_commands.Choice(name=role["name"], value=role["value"]) for role in ROLE_OPTIONS
])
@app_commands.choices(guild=[
    app_commands.Choice(name=guild["name"], value=guild["value"]) for guild in GUILD_OPTIONS
])
@app_commands.choices(vai_trò_guild=[
    app_commands.Choice(name=role["name"], value=role["value"]) for role in GUILD_ROLE_OPTIONS
])
async def setrole_command(
    interaction: discord.Interaction, 
    tên: str,
    role: app_commands.Choice[str],
    tên_nhân_vật: str,
    guild: app_commands.Choice[str],
    vai_trò_guild: app_commands.Choice[str]
):
    """Lệnh set role cho thành viên với 5 mục thông tin"""
    
    # Kiểm tra xem lệnh có được thực hiện trong chủ đề đăng ký role hoặc bởi quản trị viên không
    guild_id = interaction.guild.id
    
    # Cho phép quản trị viên sử dụng lệnh ở bất kỳ đâu
    is_admin = interaction.user.guild_permissions.administrator
    
    if guild_id not in set_role_threads:
        await interaction.response.send_message(
            "❌ Hệ thống Set Role chưa được thiết lập trong server này! Vui lòng liên hệ quản trị viên.",
            ephemeral=True
        )
        return
    
    expected_thread_id = set_role_threads[guild_id]
    
    # Nếu không phải admin và không đúng kênh, thì báo lỗi
    if not is_admin and interaction.channel.id != expected_thread_id:
        await interaction.response.send_message(
            f"❌ Lệnh này chỉ có thể sử dụng trong chủ đề đăng ký role!",
            ephemeral=True
        )
        return
    
    # Kiểm tra độ dài tên
    if len(tên) > 10:
        await interaction.response.send_message(
            "❌ Tên không được vượt quá 10 ký tự!",
            ephemeral=True
        )
        return
    
    try:
        # Lấy thông tin role đầy đủ
        role_info = next((r for r in ROLE_OPTIONS if r["value"] == role.value), None)
        if not role_info:
            await interaction.response.send_message("❌ Role không hợp lệ!", ephemeral=True)
            return
        
        # Lấy thông tin vai trò guild
        guild_role_info = next((r for r in GUILD_ROLE_OPTIONS if r["value"] == vai_trò_guild.value), None)
        if not guild_role_info:
            await interaction.response.send_message("❌ Vai trò guild không hợp lệ!", ephemeral=True)
            return
        
        # Sử dụng KÝ TỰ VIẾT TẮT cho nickname
        role_short = role_info["short_code"]
        
        # Tạo nickname mới theo định dạng: Tên-RoleShort-CharacterName-GuildEmoji
        new_nickname = create_nickname(tên, role_short, tên_nhân_vật, guild.value, guild_role_info["emoji"])
        
        # Đổi nickname cho thành viên
        nickname_changed = await change_user_nickname(interaction.user, new_nickname)
        
        # Lưu thông tin role vào database
        user_roles_db[interaction.user.id] = {
            "tên": tên,
            "role": role_info["value"],
            "role_full": role_info["full_name"],
            "role_short": role_short,
            "character_name": tên_nhân_vật,
            "guild": guild.value,
            "vai_trò_guild": guild_role_info["name"],
            "guild_role_emoji": guild_role_info["emoji"],
            "nickname": new_nickname,
            "set_at": discord.utils.utcnow().isoformat()
        }
        
        # Cấp quyền truy cập kênh chấm công
        await assign_chamcong_permissions(interaction.user, interaction.guild)
        
        # Tạo embed thông báo thành công
        embed = discord.Embed(
            title="✅ ĐĂNG KÝ ROLE THÀNH CÔNG!",
            color=0x00ff00,
            timestamp=discord.utils.utcnow()
        )
        
        # Sử dụng username gốc thay vì display_name
        embed.add_field(name="👤 Thành viên", value=interaction.user.name, inline=True)
        embed.add_field(name="📛 Tên", value=tên, inline=True)
        embed.add_field(name="🎮 Role", value=f"{role_info['full_name']} ({role_short})", inline=True)
        
        # Hiển thị thông tin xử lý tên nhân vật
        original_name = tên_nhân_vật
        processed_name = process_character_name(tên_nhân_vật)
        if original_name != processed_name:
            embed.add_field(name="🎯 Tên nhân vật", value=f"{original_name} → {processed_name}", inline=True)
        else:
            embed.add_field(name="🎯 Tên nhân vật", value=original_name, inline=True)
            
        embed.add_field(name="⚔️ Guild", value=guild.value, inline=True)
        embed.add_field(name="👑 Vai trò Guild", value=f"{guild_role_info['emoji']} {guild_role_info['name']}", inline=True)
        
        # Thông báo về trạng thái nickname
        if nickname_changed:
            embed.add_field(name="🏷️ Nickname mới", value=new_nickname, inline=False)
        else:
            embed.add_field(name="🏷️ Nickname đề xuất", value=new_nickname, inline=False)
            # Kiểm tra lý do cụ thể
            if interaction.user == interaction.guild.owner:
                embed.add_field(
                    name="ℹ️ Lưu ý đặc biệt", 
                    value="Bạn là chủ server, bot không thể đổi nickname của bạn. Vui lòng tự đổi nickname theo định dạng trên.", 
                    inline=False
                )
            elif not interaction.guild.me.guild_permissions.manage_nicknames:
                embed.add_field(
                    name="ℹ️ Lưu ý về quyền", 
                    value="Bot không có quyền 'Manage Nicknames' trong server này. Vui lòng cấp quyền cho bot hoặc tự đổi nickname.", 
                    inline=False
                )
            elif interaction.guild.me.top_role <= interaction.user.top_role:
                embed.add_field(
                    name="ℹ️ Lưu ý về vai trò", 
                    value="Role của bot không đủ cao để đổi nickname của bạn. Vui lòng nâng cao vị trí role của bot hoặc tự đổi nickname.", 
                    inline=False
                )
            else:
                embed.add_field(
                    name="ℹ️ Lưu ý", 
                    value="Bot không thể đổi nickname của bạn. Vui lòng tự đổi nickname theo định dạng trên.", 
                    inline=False
                )
            
        embed.add_field(name="🔓 Quyền truy cập", value=f"Đã cấp quyền truy cập kênh **{CHAMCONG_CHANNEL_NAME}**", inline=False)
        
        embed.set_footer(text="Bây giờ bạn đã có quyền truy cập kênh chấm công!")
        
        await interaction.response.send_message(embed=embed)
        
        print(f"✅ Đã set role cho {interaction.user.name}: {new_nickname} - Đổi nickname: {nickname_changed}")
        
    except Exception as e:
        # XỬ LÝ LỖI ĐÚNG CÁCH - KIỂM TRA XEM ĐÃ PHẢN HỒI CHƯA
        if not interaction.response.is_done():
            error_embed = discord.Embed(
                title="❌ LỖI ĐĂNG KÝ ROLE",
                color=0xff0000,
                description=f"Đã xảy ra lỗi: {str(e)}"
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
        else:
            # Nếu đã phản hồi rồi, dùng followup
            error_embed = discord.Embed(
                title="❌ LỖI ĐĂNG KÝ ROLE",
                color=0xff0000,
                description=f"Đã xảy ra lỗi: {str(e)}"
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)

@bot.tree.command(name="check_permissions", description="Kiểm tra quyền của bot")
async def check_permissions_command(interaction: discord.Interaction):
    """Kiểm tra quyền của bot"""
    permissions = interaction.guild.me.guild_permissions
    
    embed = discord.Embed(
        title="🔐 KIỂM TRA QUYỀN CỦA BOT",
        color=0x0099ff,
        timestamp=discord.utils.utcnow()
    )
    
    embed.add_field(name="Manage Nicknames", value="✅" if permissions.manage_nicknames else "❌", inline=True)
    embed.add_field(name="Change Nickname", value="✅" if permissions.change_nickname else "❌", inline=True)
    embed.add_field(name="Administrator", value="✅" if permissions.administrator else "❌", inline=True)
    embed.add_field(name="Manage Roles", value="✅" if permissions.manage_roles else "❌", inline=True)
    embed.add_field(name="Manage Channels", value="✅" if permissions.manage_channels else "❌", inline=True)
    
    # Kiểm tra vị trí role
    bot_top_role = interaction.guild.me.top_role
    user_top_role = interaction.user.top_role
    embed.add_field(name="Vị trí Role Bot", value=f"#{len(interaction.guild.roles) - bot_top_role.position}", inline=True)
    embed.add_field(name="Vị trí Role User", value=f"#{len(interaction.guild.roles) - user_top_role.position}", inline=True)
    embed.add_field(name="Bot có role cao hơn", value="✅" if bot_top_role > user_top_role else "❌", inline=True)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="myrole", description="Xem thông tin role hiện tại của bạn")
async def myrole_command(interaction: discord.Interaction):
    """Xem thông tin role hiện tại"""
    user_id = interaction.user.id
    
    if user_id in user_roles_db:
        role_data = user_roles_db[user_id]
        
        embed = discord.Embed(
            title="🎮 THÔNG TIN ROLE CỦA BẠN",
            color=0x0099ff,
            timestamp=discord.utils.utcnow()
        )
        
        # Sử dụng username gốc thay vì display_name
        embed.add_field(name="👤 Thành viên", value=interaction.user.name, inline=True)
        embed.add_field(name="📛 Tên", value=role_data["tên"], inline=True)
        embed.add_field(name="🎯 Role", value=f"{role_data['role_full']} ({role_data['role_short']})", inline=True)
        embed.add_field(name="🎮 Tên nhân vật", value=role_data["character_name"], inline=True)
        embed.add_field(name="⚔️ Guild", value=role_data["guild"], inline=True)
        embed.add_field(name="👑 Vai trò Guild", value=f"{role_data['guild_role_emoji']} {role_data['vai_trò_guild']}", inline=True)
        embed.add_field(name="🏷️ Nickname", value=role_data["nickname"], inline=True)
        
        set_time = datetime.fromisoformat(role_data["set_at"])
        embed.add_field(name="⏰ Đã đăng ký lúc", value=f"<t:{int(set_time.timestamp())}:F>", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        await interaction.response.send_message(
            "❌ Bạn chưa đăng ký role! Hãy sử dụng lệnh `/setrole` trong kênh Set Role.",
            ephemeral=True
        )

@bot.tree.command(name="reset_role", description="Reset role của thành viên (Chỉ Mod)")
@app_commands.describe(member="Thành viên cần reset role (để trống nếu reset bản thân)")
async def reset_role_command(interaction: discord.Interaction, member: discord.Member = None):
    """Reset role của thành viên (chỉ quản trị viên)"""
    if not interaction.user.guild_permissions.manage_nicknames:
        await interaction.response.send_message(
            "❌ Chỉ quản trị viên mới được sử dụng lệnh này!",
            ephemeral=True
        )
        return
    
    target_member = member or interaction.user
    target_id = target_member.id
    
    if target_id in user_roles_db:
        old_data = user_roles_db[target_id]
        
        # Reset nickname
        try:
            await target_member.edit(nick=None)
        except discord.Forbidden:
            # Nếu là quản trị viên, bỏ qua lỗi
            if not target_member.guild_permissions.administrator:
                await interaction.response.send_message(
                    "❌ Bot không có quyền đổi nickname!",
                    ephemeral=True
                )
                return
        
        # Xóa quyền truy cập kênh chấm công
        try:
            chamcong_channel = discord.utils.get(interaction.guild.text_channels, name=CHAMCONG_CHANNEL_NAME)
            if chamcong_channel:
                await chamcong_channel.set_permissions(target_member, overwrite=None)
        except Exception as e:
            print(f"⚠️ Không thể xóa quyền chấm công: {e}")
        
        # Xóa khỏi database
        del user_roles_db[target_id]
        
        embed = discord.Embed(
            title="🔄 ĐÃ RESET ROLE",
            color=0xffff00,
            description=f"Đã reset role cho {target_member.name}"
        )
        
        embed.add_field(name="🎮 Role cũ", value=f"{old_data['role_full']}", inline=True)
        embed.add_field(name="📛 Tên nhân vật cũ", value=old_data["character_name"], inline=True)
        embed.add_field(name="⚔️ Guild cũ", value=old_data["guild"], inline=True)
        embed.add_field(name="👑 Vai trò Guild cũ", value=f"{old_data['guild_role_emoji']} {old_data['vai_trò_guild']}", inline=True)
        embed.add_field(name="🔒 Quyền truy cập", value=f"Đã thu hồi quyền truy cập kênh **{CHAMCONG_CHANNEL_NAME}**", inline=False)
        
        await interaction.response.send_message(embed=embed)
        
        print(f"✅ Đã reset role cho {target_member.name}")
    else:
        await interaction.response.send_message(
            f"❌ {target_member.name} chưa có role nào được đăng ký!",
            ephemeral=True
        )

@bot.tree.command(name="fix_setrole", description="Sửa chữa hệ thống Set Role (Chỉ Admin)")
async def fix_setrole_command(interaction: discord.Interaction):
    """Sửa chữa hệ thống Set Role nếu có vấn đề"""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ Chỉ quản trị viên mới được sử dụng lệnh này!",
            ephemeral=True
        )
        return
    
    await interaction.response.send_message("🔄 Đang sửa chữa hệ thống Set Role...", ephemeral=True)
    
    # Gọi lại hàm thiết lập Set Role
    await setup_set_role_channel()
    
    # Kiểm tra kết quả
    guild_id = interaction.guild.id
    if guild_id in set_role_threads:
        thread_id = set_role_threads[guild_id]
        thread = bot.get_channel(thread_id)
        if thread:
            await interaction.followup.send(
                f"✅ Đã sửa chữa hệ thống Set Role thành công!\n"
                f"Chủ đề: {thread.mention}",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                "❌ Không thể tìm thấy chủ đề Set Role sau khi sửa chữa!",
                ephemeral=True
            )
    else:
        await interaction.followup.send(
            "❌ Không thể thiết lập hệ thống Set Role!",
            ephemeral=True
        )

# ===============================
# HỆ THỐNG CHẤM CÔNG MỚI - ĐÃ ĐIỀU CHỈNH
# ===============================

@bot.tree.command(name="chamcong", description="Chấm công báo cáo boss")
@app_commands.describe(
    boss="Tên boss đã đánh",
    ngay_thang="Ngày đánh boss (dd/mm)",
    vi_tri="Vị trí (chỉ hiện cho role Cầu Phép)",
    hinh_anh="Hình ảnh minh chứng"
)
@app_commands.choices(boss=[
    app_commands.Choice(name=boss["name"], value=boss["value"]) for boss in BOSS_LIST
])
@app_commands.choices(vi_tri=[
    app_commands.Choice(name=vt["name"], value=vt["value"]) for vt in VI_TRI_OPTIONS
])
async def chamcong_command(
    interaction: discord.Interaction, 
    boss: app_commands.Choice[str],
    ngay_thang: str,
    vi_tri: app_commands.Choice[str] = None,
    hinh_anh: discord.Attachment = None
):
    """Lệnh chấm công báo cáo boss mới"""
    # Kiểm tra xem có trong kênh chấm công không
    if interaction.channel.name != CHAMCONG_CHANNEL_NAME:
        await interaction.response.send_message(
            f"❌ Lệnh này chỉ được sử dụng trong kênh {CHAMCONG_CHANNEL_NAME}!",
            ephemeral=True
        )
        return
    
    # Kiểm tra xem user đã set role chưa
    user_id = interaction.user.id
    if user_id not in user_roles_db:
        await interaction.response.send_message(
            "❌ Bạn cần đăng ký role trước khi sử dụng lệnh chấm công!",
            ephemeral=True
        )
        return
    
    # Lấy thông tin role
    user_role_data = user_roles_db[user_id]
    nickname = user_role_data["nickname"]
    
    # Kiểm tra nếu role là Cầu Phép (CP) thì bắt buộc phải chọn vị trí
    if user_role_data["role_short"] == "CP" and vi_tri is None:
        await interaction.response.send_message(
            "❌ Với role Cầu Phép (CP), bạn phải chọn vị trí!",
            ephemeral=True
        )
        return
    
    # Kiểm tra định dạng ngày/tháng
    try:
        day, month = ngay_thang.split('/')
        day = int(day)
        month = int(month)
        # Kiểm tra ngày tháng hợp lệ
        if day < 1 or day > 31 or month < 1 or month > 12:
            raise ValueError
        # Tạo chuỗi ngày/tháng đã chuẩn hóa
        ngay_thang = f"{day:02d}/{month:02d}"
    except:
        await interaction.response.send_message(
            "❌ Định dạng ngày/tháng không hợp lệ! Hãy nhập theo dạng dd/mm (ví dụ: 15/03).",
            ephemeral=True
        )
        return
    
    # Kiểm tra ảnh đính kèm
    if hinh_anh is None:
        await interaction.response.send_message(
            "❌ Vui lòng đính kèm hình ảnh minh chứng!",
            ephemeral=True
        )
        return
    
    # Lấy URL ảnh boss từ BOSS_IMAGES
    boss_image_url = BOSS_IMAGES.get(boss.name)
    if not boss_image_url:
        # Thử tìm bằng value nếu không tìm thấy bằng name
        for boss_item in BOSS_LIST:
            if boss_item["value"] == boss.value:
                boss_image_url = BOSS_IMAGES.get(boss_item["name"])
                break
    
    # Tạo embed vé chấm công
    embed = discord.Embed(
        title="🎯 CHẤM CÔNG BOSS",
        color=0x00ff00,
        timestamp=discord.utils.utcnow()
    )
    
    # Thêm các trường thông tin theo bố cục yêu cầu
    embed.add_field(name="Boss", value=boss.name, inline=True)
    embed.add_field(name="Thành Viên", value=nickname, inline=True)
    embed.add_field(name="Thời Gian", value=ngay_thang, inline=True)
    
    # Thêm vai trò nếu có (chỉ hiển thị nếu role là CP)
    if vi_tri and user_role_data["role_short"] == "CP":
        embed.add_field(name="Vai trò", value=vi_tri.name, inline=True)
    
    # Thêm ảnh boss nếu có
    if boss_image_url:
        embed.set_thumbnail(url=boss_image_url)
    
    # Thêm ảnh đính kèm
    if hinh_anh:
        embed.set_image(url=hinh_anh.url)
    
    embed.set_footer(text=f"Chấm công bởi {interaction.user.name}")
    
    await interaction.response.send_message(embed=embed)
    
    # Gửi dữ liệu đến webhook ngay lập tức (KHÔNG CÓ NÚT DUYỆT)
    webhook_data = {
        "type": "cham_cong",
        "nickname": nickname,
        "boss": boss.name,
        "date": ngay_thang,
        "position": vi_tri.name if (vi_tri and user_role_data["role_short"] == "CP") else None,
        "image_url": hinh_anh.url,
        "timestamp": datetime.now().isoformat(),
        "user_id": str(user_id)
    }
    
    await send_to_webhook(webhook_data)
    
    print(f"✅ {nickname} đã chấm công boss {boss.name} và gửi dữ liệu đến webhook")

# ===============================
# HỆ THỐNG ĐẤU GIÁ - ĐÃ BỔ SUNG ĐẦY ĐỦ
# ===============================

@bot.tree.command(name="auction", description="Tạo phiên đấu giá mới")
@app_commands.describe(
    item_name="Tên vật phẩm đấu giá",
    start_price="Giá khởi điểm",
    duration_minutes="Thời gian đấu giá (phút)",
    boss="Tên boss (tùy chọn)"
)
@app_commands.choices(boss=[
    app_commands.Choice(name=boss["name"], value=boss["value"]) for boss in BOSS_LIST
])
async def auction_command(
    interaction: discord.Interaction,
    item_name: str,
    start_price: int,
    duration_minutes: int = 60,
    boss: str = None
):
    """Tạo phiên đấu giá mới"""
    if not interaction.user.guild_permissions.manage_messages:
        await interaction.response.send_message(
            "❌ Chỉ quản trị viên mới được sử dụng lệnh này!",
            ephemeral=True
        )
        return
    
    # Tìm vật phẩm trong danh sách
    item = None
    for auction_item in AUCTION_ITEMS:
        if auction_item["name"].lower() == item_name.lower():
            item = auction_item
            break
    
    if not item:
        await interaction.response.send_message(
            "❌ Vật phẩm không tồn tại trong danh sách!",
            ephemeral=True
        )
        return
    
    # Tạo thread cho đấu giá
    thread_name = f"Đấu giá - {item_name}"
    try:
        thread = await interaction.channel.create_thread(
            name=thread_name,
            type=discord.ChannelType.public_thread,
            reason=f"Đấu giá vật phẩm {item_name}"
        )
        
        # Tạo auction record
        auction_id = f"{interaction.guild.id}_{int(datetime.now().timestamp())}"
        end_time = discord.utils.utcnow() + timedelta(minutes=duration_minutes)
        
        auctions_db[auction_id] = {
            'item': item,
            'start_price': start_price,
            'current_price': start_price,
            'last_bidder': None,
            'end_time': end_time,
            'thread_id': thread.id,
            'creator': interaction.user.id,
            'boss': boss,
            'bids': [],
            'ended': False
        }
        
        # Tạo embed thông báo auction
        embed = discord.Embed(
            title=f"🎯 PHIÊN ĐẤU GIÁ BẮT ĐẦU",
            color=0xffd700,
            timestamp=discord.utils.utcnow()
        )
        
        # Sử dụng name thay vì mention
        creator_name = interaction.user.name
        embed.add_field(name="👤 Người tạo", value=creator_name, inline=True)
        embed.add_field(name="📦 Vật phẩm", value=f"{item['emoji']} {item['name']}", inline=True)
        embed.add_field(name="💰 Giá khởi điểm", value=f"{start_price:,} 💎", inline=True)
        embed.add_field(name="⏰ Thời gian kết thúc", value=f"<t:{int(end_time.timestamp())}:R>", inline=True)
        
        if boss:
            embed.add_field(name="🎯 Boss", value=boss, inline=True)
        
        embed.add_field(
            name="📝 Hướng dẫn đấu giá",
            value=(
                "Sử dụng lệnh `/bid <số_tiền>` để tham gia đấu giá.\n"
                "Bước giá tối thiểu: 10% giá hiện tại.\n"
                "Người thắng cuộc sẽ là người đặt giá cao nhất khi kết thúc."
            ),
            inline=False
        )
        
        # Thêm ảnh vật phẩm nếu có
        if item.get('image_url'):
            embed.set_image(url=item['image_url'])
        
        embed.set_footer(text=f"ID: {auction_id}")
        
        await thread.send(embed=embed)
        await interaction.response.send_message(
            f"✅ Đã tạo phiên đấu giá: {thread.mention}",
            ephemeral=True
        )
        
    except Exception as e:
        await interaction.response.send_message(
            f"❌ Lỗi khi tạo phiên đấu giá: {e}",
            ephemeral=True
        )

@bot.tree.command(name="bid", description="Đặt giá trong phiên đấu giá")
@app_commands.describe(amount="Số tiền đặt giá")
async def bid_command(interaction: discord.Interaction, amount: int):
    """Đặt giá trong phiên đấu giá"""
    # Tìm auction đang active trong thread này
    auction = None
    auction_id = None
    
    for aid, auc in auctions_db.items():
        if auc['thread_id'] == interaction.channel.id and not auc.get('ended', False):
            auction = auc
            auction_id = aid
            break
    
    if not auction:
        await interaction.response.send_message(
            "❌ Không tìm thấy phiên đấu giá đang hoạt động trong thread này!",
            ephemeral=True
        )
        return
    
    # Kiểm tra giá
    min_bid = auction['current_price'] * 1.1  # Bước giá tối thiểu 10%
    
    if amount < min_bid:
        await interaction.response.send_message(
            f"❌ Giá đặt tối thiểu là {int(min_bid):,} 💎!",
            ephemeral=True
        )
        return
    
    # Cập nhật giá
    old_price = auction['current_price']
    auction['current_price'] = amount
    auction['last_bidder'] = interaction.user.id
    auction['bids'].append({
        'user_id': interaction.user.id,
        'amount': amount,
        'timestamp': discord.utils.utcnow()
    })
    
    # Tạo embed thông báo đặt giá thành công
    embed = discord.Embed(
        title="✅ ĐẶT GIÁ THÀNH CÔNG",
        color=0x00ff00,
        timestamp=discord.utils.utcnow()
    )
    
    # Sử dụng name thay vì mention
    bidder_name = interaction.user.name
    embed.add_field(name="👤 Người đặt giá", value=bidder_name, inline=True)
    embed.add_field(name="💰 Giá cũ", value=f"{old_price:,} 💎", inline=True)
    embed.add_field(name="💰 Giá mới", value=f"{amount:,} 💎", inline=True)
    
    time_remaining = auction['end_time'] - discord.utils.utcnow()
    minutes_remaining = int(time_remaining.total_seconds() // 60)
    seconds_remaining = int(time_remaining.total_seconds() % 60)
    
    embed.add_field(
        name="⏰ Thời gian còn lại",
        value=f"{minutes_remaining} phút {seconds_remaining} giây",
        inline=False
    )
    
    await interaction.response.send_message(embed=embed)
    
    # Gửi thông báo cho mọi người về giá mới
    alert_embed = discord.Embed(
        title="🎯 CÓ NGƯỜI ĐẶT GIÁ MỚI!",
        color=0xffa500,
        description=f"Giá hiện tại: **{amount:,} 💎**"
    )
    
    alert_embed.add_field(name="👤 Người đặt", value=bidder_name, inline=True)
    alert_embed.add_field(name="⏰ Kết thúc sau", value=f"{minutes_remaining} phút", inline=True)
    
    await interaction.channel.send(embed=alert_embed)

@bot.tree.command(name="end_auction", description="Kết thúc phiên đấu giá sớm (Chỉ Admin)")
@app_commands.describe(auction_id="ID của phiên đấu giá (xem trong footer của tin nhắn auction)")
async def end_auction_command(interaction: discord.Interaction, auction_id: str):
    """Kết thúc phiên đấu giá sớm"""
    if not interaction.user.guild_permissions.manage_messages:
        await interaction.response.send_message(
            "❌ Chỉ quản trị viên mới được sử dụng lệnh này!",
            ephemeral=True
        )
        return
    
    if auction_id not in auctions_db:
        await interaction.response.send_message(
            "❌ Không tìm thấy phiên đấu giá với ID này!",
            ephemeral=True
        )
        return
    
    auction = auctions_db[auction_id]
    
    # Kiểm tra xem auction đã kết thúc chưa
    if auction.get('ended', False):
        await interaction.response.send_message(
            "❌ Phiên đấu giá này đã kết thúc!",
            ephemeral=True
        )
        return
    
    # Kết thúc auction
    auction['ended'] = True
    auction['end_time'] = discord.utils.utcnow()
    
    # Lấy thread
    thread = bot.get_channel(auction['thread_id'])
    if thread:
        # Xóa tin nhắn đếm ngược cũ nếu có
        if auction['thread_id'] in countdown_messages:
            try:
                old_msg = await thread.fetch_message(countdown_messages[auction['thread_id']])
                await old_msg.delete()
            except:
                pass
            del countdown_messages[auction['thread_id']]
        
        # Khoá thread
        await thread.edit(locked=True, archived=True)
        
        # Thông báo người thắng cuộc
        if auction.get('last_bidder'):
            winner = bot.get_user(auction['last_bidder'])
            if winner:
                winner_name = winner.name
                await thread.send(f"🎉 **NGƯỜI THẮNG CUỘC: 🏆 {winner_name} 🏆 VỚI GIÁ {auction['current_price']:,} 💎**")
            else:
                await thread.send(f"🎉 **NGƯỜI THẮNG CUỐC: <@{auction['last_bidder']}> VỚI GIÁ {auction['current_price']:,} 💎!**")
        else:
            await thread.send("❌ **KHÔNG CÓ AI ĐẤU GIÁ!**")
        
        await thread.send("🛑 **PHIÊN ĐẤU GIÁ ĐÃ KẾT THÚC SỚM BỞI QUẢN TRỊ VIÊN!**")
    
    await interaction.response.send_message(
        f"✅ Đã kết thúc phiên đấu giá {auction_id}!",
        ephemeral=True
    )

@bot.tree.command(name="auction_stats", description="Xem thống kê các phiên đấu giá")
async def auction_stats_command(interaction: discord.Interaction):
    """Xem thống kê auction"""
    active_auctions = []
    ended_auctions = []
    
    for auction_id, auction in auctions_db.items():
        if auction.get('ended', False):
            ended_auctions.append(auction)
        else:
            active_auctions.append(auction)
    
    embed = discord.Embed(
        title="📊 THỐNG KÊ ĐẤU GIÁ",
        color=0x0099ff,
        timestamp=discord.utils.utcnow()
    )
    
    embed.add_field(name="🟢 Đang hoạt động", value=f"{len(active_auctions)} phiên", inline=True)
    embed.add_field(name="🔴 Đã kết thúc", value=f"{len(ended_auctions)} phiên", inline=True)
    embed.add_field(name="📈 Tổng cộng", value=f"{len(auctions_db)} phiên", inline=True)
    
    # Hiển thị auction đang active
    if active_auctions:
        active_text = ""
        for auction in active_auctions[:5]:  # Giới hạn hiển thị 5 auction
            item = auction['item']
            time_remaining = auction['end_time'] - discord.utils.utcnow()
            minutes = int(time_remaining.total_seconds() // 60)
            seconds = int(time_remaining.total_seconds() % 60)
            
            # Hiển thị thông tin người đặt giá cuối
            last_bidder_info = ""
            if auction.get('last_bidder'):
                bidder = bot.get_user(auction['last_bidder'])
                if bidder:
                    last_bidder_info = f" - {bidder.name}"
                else:
                    last_bidder_info = f" - <@{auction['last_bidder']}>"
            
            active_text += f"• {item['emoji']} **{item['name']}** - {auction['current_price']:,} 💎{last_bidder_info} - Còn {minutes}p{seconds}s\n"
        
        if len(active_auctions) > 5:
            active_text += f"... và {len(active_auctions) - 5} phiên khác"
        
        embed.add_field(name="🎯 Đấu giá đang diễn ra", value=active_text, inline=False)
    else:
        embed.add_field(name="🎯 Đấu giá đang diễn ra", value="*Không có phiên đấu giá nào đang hoạt động*", inline=False)
    
    # Hiển thị auction đã kết thúc gần đây
    recent_ended = ended_auctions[-3:]  # 3 auction gần nhất
    if recent_ended:
        ended_text = ""
        for auction in recent_ended:
            item = auction['item']
            winner_info = "Không có người thắng"
            if auction.get('last_bidder'):
                winner = bot.get_user(auction['last_bidder'])
                if winner:
                    winner_info = winner.name
                else:
                    winner_info = f"<@{auction['last_bidder']}>"
            
            ended_text += f"• {item['emoji']} **{item['name']}** - {auction['current_price']:,} 💎 - 🏆{winner_info}\n"
        
        embed.add_field(name="📝 Kết thúc gần đây", value=ended_text, inline=False)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="active_auctions", description="Xem danh sách các phiên đấu giá đang hoạt động")
async def active_auctions_command(interaction: discord.Interaction):
    """Xem danh sách auction đang hoạt động"""
    active_auctions = [auction for auction in auctions_db.values() if not auction.get('ended', False)]
    
    if not active_auctions:
        embed = discord.Embed(
            title="📋 DANH SÁCH ĐẤU GIÁ ĐANG HOẠT ĐỘNG",
            description="*Hiện không có phiên đấu giá nào đang diễn ra*",
            color=0xffff00
        )
        await interaction.response.send_message(embed=embed)
        return
    
    embed = discord.Embed(
        title="📋 DANH SÁCH ĐẤU GIÁ ĐANG HOẠT ĐỘNG",
        color=0x00ff00,
        timestamp=discord.utils.utcnow()
    )
    
    for i, auction in enumerate(active_auctions, 1):
        item = auction['item']
        time_remaining = auction['end_time'] - discord.utils.utcnow()
        minutes = int(time_remaining.total_seconds() // 60)
        seconds = int(time_remaining.total_seconds() % 60)
        
        # Lấy thông tin người đặt giá cuối
        last_bidder_info = "Chưa có ai đặt giá"
        if auction.get('last_bidder'):
            bidder = bot.get_user(auction['last_bidder'])
            if bidder:
                last_bidder_info = bidder.name
            else:
                last_bidder_info = f"<@{auction['last_bidder']}>"
        
        # Lấy thread để có link
        thread = bot.get_channel(auction['thread_id'])
        thread_mention = thread.mention if thread else "Không tìm thấy"
        
        embed.add_field(
            name=f"{i}. {item['emoji']} {item['name']}",
            value=(
                f"💰 **Giá hiện tại:** {auction['current_price']:,} 💎\n"
                f"👤 **Người đặt giá cuối:** {last_bidder_info}\n"
                f"⏰ **Thời gian còn lại:** {minutes} phút {seconds} giây\n"
                f"🔗 **Tham gia:** {thread_mention}\n"
                f"🎯 **Boss:** {auction.get('boss', 'Không xác định')}"
            ),
            inline=False
        )
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="bid_history", description="Xem lịch sử đặt giá của phiên đấu giá hiện tại")
async def bid_history_command(interaction: discord.Interaction):
    """Xem lịch sử đặt giá trong thread đấu giá hiện tại"""
    # Tìm auction đang active trong thread này
    auction = None
    
    for auc in auctions_db.values():
        if auc['thread_id'] == interaction.channel.id and not auc.get('ended', False):
            auction = auc
            break
    
    if not auction:
        await interaction.response.send_message(
            "❌ Không tìm thấy phiên đấu giá đang hoạt động trong thread này!",
            ephemeral=True
        )
        return
    
    bids = auction.get('bids', [])
    
    if not bids:
        embed = discord.Embed(
            title="📜 LỊCH SỬ ĐẶT GIÁ",
            description="*Chưa có lần đặt giá nào trong phiên đấu giá này*",
            color=0xffff00
        )
        await interaction.response.send_message(embed=embed)
        return
    
    embed = discord.Embed(
        title="📜 LỊCH SỬ ĐẶT GIÁ",
        color=0x0099ff,
        timestamp=discord.utils.utcnow()
    )
    
    # Hiển thị 10 bid gần nhất (đảo ngược để mới nhất lên đầu)
    recent_bids = list(reversed(bids))[:10]
    
    for i, bid in enumerate(recent_bids, 1):
        bidder = bot.get_user(bid['user_id'])
        bidder_name = bidder.name if bidder else f"<@{bid['user_id']}>"
        
        time_ago = discord.utils.utcnow() - bid['timestamp']
        minutes_ago = int(time_ago.total_seconds() // 60)
        
        embed.add_field(
            name=f"#{len(bids) - i + 1} - {bidder_name}",
            value=f"💰 {bid['amount']:,} 💎 - {minutes_ago} phút trước",
            inline=False
        )
    
    embed.set_footer(text=f"Tổng cộng {len(bids)} lần đặt giá")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="item_list", description="Xem danh sách vật phẩm có thể đấu giá")
async def item_list_command(interaction: discord.Interaction):
    """Xem danh sách vật phẩm đấu giá"""
    if not AUCTION_ITEMS:
        await interaction.response.send_message(
            "❌ Danh sách vật phẩm trống!",
            ephemeral=True
        )
        return
    
    embed = discord.Embed(
        title="📦 DANH SÁCH VẬT PHẨM ĐẤU GIÁ",
        color=0x0099ff,
        timestamp=discord.utils.utcnow()
    )
    
    # Nhóm vật phẩm theo category
    items_by_category = {}
    for item in AUCTION_ITEMS:
        category = item.get('category', 'khác')
        if category not in items_by_category:
            items_by_category[category] = []
        items_by_category[category].append(item)
    
    for category, items in items_by_category.items():
        category_text = ""
        for item in items[:10]:  # Giới hạn 10 vật phẩm mỗi category
            category_text += f"{item['emoji']} **{item['name']}**\n"
        
        if len(items) > 10:
            category_text += f"... và {len(items) - 10} vật phẩm khác"
        
        embed.add_field(
            name=f"🎯 {category.upper()}",
            value=category_text,
            inline=True
        )
    
    embed.set_footer(text=f"Tổng cộng {len(AUCTION_ITEMS)} vật phẩm")
    await interaction.response.send_message(embed=embed)

# ===============================
# LỆNH QUẢN LÝ KHÁC
# ===============================

@bot.tree.command(name="ping", description="Kiểm tra độ trễ của bot")
async def ping_command(interaction: discord.Interaction):
    """Kiểm tra ping của bot"""
    latency = round(bot.latency * 1000)
    
    embed = discord.Embed(
        title="🏓 PONG!",
        color=0x00ff00,
        description=f"Độ trễ: **{latency}ms**"
    )
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="server_info", description="Xem thông tin server")
async def server_info_command(interaction: discord.Interaction):
    """Xem thông tin server"""
    guild = interaction.guild
    
    embed = discord.Embed(
        title=f"🏠 THÔNG TIN SERVER - {guild.name}",
        color=0x0099ff,
        timestamp=discord.utils.utcnow()
    )
    
    # Sử dụng name cho chủ server
    owner_name = guild.owner.name
    embed.add_field(name="👑 Chủ server", value=owner_name, inline=True)
    embed.add_field(name="🆔 Server ID", value=guild.id, inline=True)
    embed.add_field(name="👥 Số thành viên", value=guild.member_count, inline=True)
    embed.add_field(name="📅 Tạo ngày", value=f"<t:{int(guild.created_at.timestamp())}:D>", inline=True)
    embed.add_field(name="📊 Số kênh", value=len(guild.channels), inline=True)
    embed.add_field(name="🎭 Số role", value=len(guild.roles), inline=True)
    
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    
    await interaction.response.send_message(embed=embed)

# ===============================
# CHẠY BOT TRÊN RENDER
# ===============================

if __name__ == "__main__":
    # Lấy token từ biến môi trường (Render)
    token = os.getenv('DISCORD_TOKEN')
    
    if not token:
        print("❌ Không tìm thấy DISCORD_TOKEN!")
        print("👉 Hãy đặt token trong biến môi trường DISCORD_TOKEN")
        print("👉 Trên Render: Settings -> Environment Variables")
    else:
        print("🚀 Đang khởi động bot trên Render...")
        print(f"🌐 Webhook URL: {WEBHOOK_URL}")
        bot.run(token)
