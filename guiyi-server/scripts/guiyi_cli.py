#!/usr/bin/env python3
"""
GuiYi CLI - 命令行测试工具
"""

import click
import httpx
import json
from pathlib import Path


@click.group()
def cli():
    """GuiYi 命令行工具"""
    pass


@cli.command()
@click.argument('url')
def save(url):
    """保存网页链接"""
    api_url = "http://localhost:8765/api/save"

    try:
        response = httpx.post(api_url, json={"url": url}, timeout=30.0)
        response.raise_for_status()

        result = response.json()
        click.echo("✓ 保存成功！")
        click.echo(f"标题: {result['title']}")
        click.echo(f"文件: {result['file_path']}")
        click.echo(f"文档 ID: {result['doc_id']}")

    except httpx.ConnectError:
        click.echo("✗ 无法连接到后端服务，请确保服务已启动", err=True)
    except Exception as e:
        click.echo(f"✗ 保存失败: {e}", err=True)


@cli.command()
@click.argument('query')
@click.option('--source', '-s', help='数据源筛选 (web/feishu/wps)')
@click.option('--limit', '-l', default=10, help='返回结果数量')
def search(query, source, limit):
    """语义搜索"""
    api_url = "http://localhost:8765/api/search"

    try:
        payload = {
            "query": query,
            "source": source,
            "limit": limit
        }

        response = httpx.post(api_url, json=payload, timeout=10.0)
        response.raise_for_status()

        results = response.json()

        if not results:
            click.echo("未找到相关文档")
            return

        click.echo(f"\n找到 {len(results)} 个结果:\n")
        for i, result in enumerate(results, 1):
            click.echo(f"{i}. {result['title']}")
            click.echo(f"   来源: {result['source']}")
            click.echo(f"   URL: {result['url']}")
            click.echo(f"   相关度: {result['score']:.2f}")
            click.echo(f"   摘要: {result['text'][:100]}...")
            click.echo()

    except httpx.ConnectError:
        click.echo("✗ 无法连接到后端服务，请确保服务已启动", err=True)
    except Exception as e:
        click.echo(f"✗ 搜索失败: {e}", err=True)


@cli.command()
def status():
    """查看服务状态"""
    api_url = "http://localhost:8765/api/status"

    try:
        response = httpx.get(api_url, timeout=5.0)
        response.raise_for_status()

        result = response.json()
        click.echo("✓ 服务运行中")
        click.echo(f"运行时间: {result['uptime']:.0f} 秒")
        click.echo(f"支持的数据源: {', '.join(result['sources'])}")
        click.echo(f"\n存储信息:")
        click.echo(f"  文件总数: {result['storage']['total_files']}")
        click.echo(f"  存储大小: {result['storage']['total_size_mb']} MB")
        click.echo(f"\n索引信息:")
        click.echo(f"  文档总数: {result['index']['total_documents']}")
        click.echo(f"  向量模型: {result['index']['model']}")

    except httpx.ConnectError:
        click.echo("✗ 后端服务未运行", err=True)
    except Exception as e:
        click.echo(f"✗ 获取状态失败: {e}", err=True)


@cli.command()
def files():
    """列出已保存的文件"""
    api_url = "http://localhost:8765/api/files"

    try:
        response = httpx.get(api_url, timeout=5.0)
        response.raise_for_status()

        result = response.json()
        click.echo(f"共 {result['total']} 个文件:\n")
        for filename in result['files']:
            click.echo(f"  - {filename}")

    except httpx.ConnectError:
        click.echo("✗ 无法连接到后端服务，请确保服务已启动", err=True)
    except Exception as e:
        click.echo(f"✗ 获取文件列表失败: {e}", err=True)


if __name__ == '__main__':
    cli()
