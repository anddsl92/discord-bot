# Đọc file anhboss.txt
def load_boss_images():
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
    except Exception as e:
        print(f"❌ Lỗi khi đọc file anhboss.txt: {e}")
    return boss_images

BOSS_IMAGES = load_boss_images()

# Cập nhật danh sách boss cho lệnh chamcong
BOSS_LIST_CHAMCONG = [
    {"name": "Orfen", "value": "orfen"},
    {"name": "Orfen Xâm Lược", "value": "orfen_xam_luoc"},
    {"name": "Silla", "value": "silla"},
    {"name": "Murf", "value": "murf"},
    {"name": "Normus", "value": "normus"},
    {"name": "Ukanba", "value": "ukanba"},
    {"name": "Selihorden", "value": "selihorden"}
]

# Lệnh chamcong mới
@bot.tree.command(name="chamcong", description="Báo cáo boss đã đánh")
@app_commands.describe(
    boss="Tên boss đã đánh",
    ngay_thang="Ngày đánh boss (dd/mm)",
    vi_tri="Vị trí (nếu có)",
    hinh_anh="Hình ảnh minh chứng (tải lên ảnh)"
)
@app_commands.choices(boss=[
    app_commands.Choice(name=boss["name"], value=boss["value"]) for boss in BOSS_LIST_CHAMCONG
])
@app_commands.choices(vi_tri=[
    app_commands.Choice(name="Buff+Khiên", value="buff_khien"),
    app_commands.Choice(name="Hồi Máu Đơn", value="hoi_mau_don")
])
async def chamcong_command(
    interaction: discord.Interaction, 
    boss: app_commands.Choice[str],
    ngay_thang: str,
    vi_tri: app_commands.Choice[str] = None,
    hinh_anh: discord.Attachment = None
):
    """Lệnh báo cáo boss mới"""
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

    # Lấy nickname từ user_roles_db
    user_role_data = user_roles_db[user_id]
    nickname = user_role_data.get("nickname", interaction.user.display_name)

    # Kiểm tra nếu role là Cầu Phép (CP) thì bắt buộc phải chọn vị trí
    if user_role_data.get("role_short") == "CP" and vi_tri is None:
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
        # Tạo chuỗi ngày/tháng đã chuẩn hóa (đảm bảo có 2 chữ số cho ngày và tháng)
        ngay_thang = f"{day:02d}/{month:02d}"
    except:
        await interaction.response.send_message(
            "❌ Định dạng ngày/tháng không hợp lệ! Hãy nhập theo dạng dd/mm (ví dụ: 15/03).",
            ephemeral=True
        )
        return

    # Lấy URL ảnh boss từ BOSS_IMAGES
    boss_image_url = BOSS_IMAGES.get(boss.name)
    if not boss_image_url:
        boss_image_url = BOSS_IMAGES.get(boss.value)  # Thử với value nếu không tìm thấy bằng name

    # Tạo embed báo cáo boss
    embed = discord.Embed(
        title="🎯 BÁO CÁO BOSS",
        color=0x0099ff,
        timestamp=discord.utils.utcnow()
    )

    # Thêm các trường thông tin
    embed.add_field(name="Boss", value=boss.name, inline=True)
    embed.add_field(name="Thành Viên", value=nickname, inline=True)
    embed.add_field(name="Thời Gian", value=ngay_thang, inline=True)

    # Nếu có vị trí thì thêm vào
    if vi_tri:
        embed.add_field(name="Vai trò", value=vi_tri.name, inline=True)

    # Thêm ảnh boss nếu có
    if boss_image_url:
        embed.set_thumbnail(url=boss_image_url)

    # Xử lý ảnh đính kèm
    image_url = None
    if hinh_anh:
        image_url = hinh_anh.url
        embed.set_image(url=image_url)

    # Thêm footer
    embed.set_footer(text=f"Báo cáo bởi {interaction.user.name}")

    # Gửi embed
    await interaction.response.send_message(embed=embed)

    # Lưu thông tin boss chờ duyệt (nếu cần cho webhook sau này)
    # ... (phần này có thể giữ nguyên như cũ nếu vẫn cần duyệt)
