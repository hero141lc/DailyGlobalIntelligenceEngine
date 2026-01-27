"""
邮件发送模块
支持 SMTP 发送 HTML 邮件
支持多个收件人
"""
import smtplib
import socket
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List, Union

from config import settings
from utils.logger import logger

def send_email(html_content: str, subject: str = None, recipients: Union[str, List[str], None] = None) -> bool:
    """
    发送 HTML 邮件（支持多个收件人）
    
    Args:
        html_content: HTML 邮件内容
        subject: 邮件主题，默认使用日期
        recipients: 收件人列表，如果为 None 则使用配置中的 RECIPIENT_EMAIL
    
    Returns:
        发送成功返回 True，失败返回 False
    """
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        logger.error("未配置邮件账户信息")
        logger.error(f"SMTP_USER: {'已配置' if settings.SMTP_USER else '未配置'}")
        logger.error(f"SMTP_PASSWORD: {'已配置' if settings.SMTP_PASSWORD else '未配置'}")
        logger.error("请检查 GitHub Secrets 中的 SMTP_USER 和 SMTP_PASS 是否正确配置")
        return False
    
    # 验证 SMTP_HOST 配置
    smtp_host = settings.SMTP_HOST.strip() if settings.SMTP_HOST else "smtp.gmail.com"
    smtp_port = settings.SMTP_PORT
    
    if not smtp_host:
        logger.error("SMTP_HOST 未配置，使用默认值 smtp.gmail.com")
        smtp_host = "smtp.gmail.com"
    
    logger.debug(f"SMTP 配置: {smtp_host}:{smtp_port}")
    
    # 确定收件人列表
    if recipients is None:
        recipients = settings.RECIPIENT_EMAIL
    
    # 统一转换为列表格式
    if isinstance(recipients, str):
        recipients = [email.strip() for email in recipients.split(",") if email.strip()]
    elif not isinstance(recipients, list):
        recipients = [recipients]
    
    if not recipients:
        logger.error("未配置收件邮箱")
        return False
    
    if not subject:
        from utils.time import get_today_date
        subject = f"全球科技与金融情报速览 - {get_today_date()}"
    
    try:
        # 创建邮件对象
        msg = MIMEMultipart("alternative")
        msg["From"] = settings.SMTP_USER
        msg["To"] = ", ".join(recipients)  # 多个收件人用逗号分隔
        msg["Subject"] = subject
        
        # 添加 HTML 内容
        html_part = MIMEText(html_content, "html", "utf-8")
        msg.attach(html_part)
        
        # 发送邮件
        if len(recipients) == 1:
            logger.info(f"正在发送邮件到 {recipients[0]}...")
        else:
            logger.info(f"正在发送邮件到 {len(recipients)} 个收件人: {', '.join(recipients)}...")
        
        # 创建 SMTP 连接
        logger.info(f"连接 SMTP 服务器 {smtp_host}:{smtp_port}...")
        
        # 使用上下文管理器自动处理连接和关闭
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
            # 启用调试模式（可选，用于排查问题）
            # server.set_debuglevel(1)
            
            # 启用 TLS
            logger.info("启用 TLS...")
            server.starttls()
            
            # 登录
            logger.info("登录 SMTP 服务器...")
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            
            # 发送邮件（使用 sendmail 支持多个收件人）
            logger.info("发送邮件...")
            server.sendmail(settings.SMTP_USER, recipients, msg.as_string())
        
        # 连接已自动关闭（上下文管理器）
        if len(recipients) == 1:
            logger.info(f"邮件发送成功到 {recipients[0]}")
        else:
            logger.info(f"邮件发送成功到 {len(recipients)} 个收件人")
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"邮件认证失败: {e}")
        logger.error("请检查 SMTP_USER 和 SMTP_PASSWORD 是否正确")
        
        # Gmail 特殊提示（推荐）
        if "gmail.com" in settings.SMTP_HOST:
            logger.error("")
            logger.error("⚠️  Gmail 需要使用应用专用密码，不是账户密码！")
            logger.error("   获取步骤：")
            logger.error("   1. 登录 https://myaccount.google.com/security")
            logger.error("   2. 启用两步验证（如果未启用）")
            logger.error("   3. 进入 '应用密码' 或 'App passwords'")
            logger.error("   4. 生成新的应用密码（选择 '邮件' 和 '其他设备'）")
            logger.error("   5. 将生成的 16 位密码（无连字符）配置到 SMTP_PASS")
            logger.error("   注意：应用密码是 16 位字符，不包含连字符")
        
        # Outlook/Office365 提示（已禁用基本认证）
        elif "outlook.com" in settings.SMTP_HOST or "office365.com" in settings.SMTP_HOST:
            logger.error("")
            logger.error("⚠️  Outlook/Office365 已禁用基本认证，无法使用 SMTP 基本认证！")
            logger.error("   建议：改用 Gmail（支持基本认证，配置更简单）")
            logger.error("   如需继续使用 Outlook，需要使用 OAuth2（复杂，不推荐）")
        
        return False
    except (socket.gaierror, OSError) as e:
        logger.error(f"SMTP 连接错误（DNS 解析失败）: {e}")
        logger.error(f"当前 SMTP_HOST: '{smtp_host}'")
        logger.error(f"当前 SMTP_PORT: {smtp_port}")
        logger.error("")
        logger.error("可能的原因：")
        logger.error("1. SMTP_HOST 环境变量未配置或为空")
        logger.error("2. SMTP_HOST 配置的主机名无效")
        logger.error("3. GitHub Actions 网络环境无法解析该主机名")
        logger.error("")
        logger.error("解决方案：")
        logger.error("1. 在 GitHub Secrets 中配置 SMTP_HOST（例如：smtp.gmail.com）")
        logger.error("2. 如果使用 Gmail，确保 SMTP_HOST=smtp.gmail.com")
        logger.error("3. 如果未配置 SMTP_HOST，系统会使用默认值 smtp.gmail.com")
        return False
    except smtplib.SMTPException as e:
        logger.error(f"SMTP 错误: {e}")
        logger.error(f"SMTP 错误详情: {type(e).__name__}: {str(e)}")
        return False
    except ConnectionError as e:
        logger.error(f"SMTP 连接错误: {e}")
        logger.error(f"请检查 SMTP_HOST ({smtp_host}) 和 SMTP_PORT ({smtp_port}) 是否正确")
        return False
    except Exception as e:
        logger.error(f"发送邮件失败: {e}")
        logger.error(f"错误类型: {type(e).__name__}")
        import traceback
        logger.error(f"错误详情: {traceback.format_exc()}")
        return False

def send_report(html_content: str) -> bool:
    """
    发送报告邮件（便捷方法）
    
    Args:
        html_content: HTML 报告内容
    
    Returns:
        发送成功返回 True，失败返回 False
    """
    return send_email(html_content)

