// 数据库管理页面JavaScript

class DatabaseManager {
    constructor() {
        this.currentTable = null;
        this.currentPage = 1;
        this.pageSize = 20;
        this.tablesInfo = {};
        this.currentData = [];
        this.editingItem = null;
        
        this.init();
    }
    
    async init() {
        this.bindEvents();
        await this.loadTablesInfo();
        await this.loadStats();
    }
    
    bindEvents() {
        // 刷新统计按钮
        document.getElementById('refresh-stats').addEventListener('click', () => {
            this.loadStats();
        });
        
        // 搜索功能
        document.getElementById('search-btn').addEventListener('click', () => {
            this.searchData();
        });
        
        document.getElementById('search-input').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.searchData();
            }
        });
        
        // 新增记录按钮
        document.getElementById('add-record-btn').addEventListener('click', () => {
            this.showRecordModal();
        });
        
        // 刷新数据按钮
        document.getElementById('refresh-data-btn').addEventListener('click', () => {
            this.loadTableData();
        });
        
        // 模态框事件
        document.getElementById('modal-close').addEventListener('click', () => {
            this.hideRecordModal();
        });
        
        document.getElementById('cancel-btn').addEventListener('click', () => {
            this.hideRecordModal();
        });
        
        document.getElementById('record-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.saveRecord();
        });
        
        // 删除确认模态框事件
        document.getElementById('delete-modal-close').addEventListener('click', () => {
            this.hideDeleteModal();
        });
        
        document.getElementById('cancel-delete-btn').addEventListener('click', () => {
            this.hideDeleteModal();
        });
        
        document.getElementById('confirm-delete-btn').addEventListener('click', () => {
            this.confirmDelete();
        });
        
        // 点击模态框外部关闭
        window.addEventListener('click', (e) => {
            const recordModal = document.getElementById('record-modal');
            const deleteModal = document.getElementById('delete-modal');
            
            if (e.target === recordModal) {
                this.hideRecordModal();
            }
            if (e.target === deleteModal) {
                this.hideDeleteModal();
            }
        });
    }
    
    async loadTablesInfo() {
        try {
            const response = await fetch('/api/db-management/tables');
            if (!response.ok) {
                throw new Error('获取表信息失败');
            }
            
            this.tablesInfo = await response.json();
            this.renderTableButtons();
        } catch (error) {
            this.showMessage('获取表信息失败: ' + error.message, 'error');
        }
    }
    
    async loadStats() {
        try {
            const response = await fetch('/api/db-management/stats');
            if (!response.ok) {
                throw new Error('获取统计信息失败');
            }
            
            const stats = await response.json();
            this.renderStats(stats);
        } catch (error) {
            this.showMessage('获取统计信息失败: ' + error.message, 'error');
        }
    }
    
    renderStats(stats) {
        const statsGrid = document.getElementById('stats-grid');
        statsGrid.innerHTML = '';
        
        for (const [tableName, tableStats] of Object.entries(stats)) {
            const tableInfo = this.tablesInfo[tableName];
            if (!tableInfo) continue;
            
            const statCard = document.createElement('div');
            statCard.className = 'stat-card';
            
            let details = '';
            if (tableName === 'images') {
                details = `已下载: ${tableStats.downloaded} | 活跃: ${tableStats.active}`;
            } else if (tableName === 'crawl_sessions') {
                details = `已完成: ${tableStats.completed} | 运行中: ${tableStats.running}`;
            } else {
                details = `活跃: ${tableStats.active || tableStats.total}`;
            }
            
            statCard.innerHTML = `
                <h3>${tableInfo.name}</h3>
                <div class="stat-number">${tableStats.total}</div>
                <div class="stat-details">${details}</div>
            `;
            
            statsGrid.appendChild(statCard);
        }
    }
    
    renderTableButtons() {
        const tableButtons = document.getElementById('table-buttons');
        tableButtons.innerHTML = '';
        
        for (const [tableName, tableInfo] of Object.entries(this.tablesInfo)) {
            const button = document.createElement('div');
            button.className = 'table-button';
            button.dataset.table = tableName;
            
            button.innerHTML = `
                <h3>${tableInfo.name}</h3>
                <p>${tableInfo.description}</p>
            `;
            
            button.addEventListener('click', () => {
                this.selectTable(tableName);
            });
            
            tableButtons.appendChild(button);
        }
    }
    
    selectTable(tableName) {
        // 更新按钮状态
        document.querySelectorAll('.table-button').forEach(btn => {
            btn.classList.remove('active');
        });
        document.querySelector(`[data-table="${tableName}"]`).classList.add('active');
        
        // 设置当前表
        this.currentTable = tableName;
        this.currentPage = 1;
        
        // 更新标题
        document.getElementById('current-table-title').textContent = 
            `${this.tablesInfo[tableName].name} 管理`;
        
        // 显示数据面板
        document.getElementById('data-panel').style.display = 'block';
        
        // 加载数据
        this.loadTableData();
    }
    
    async loadTableData() {
        if (!this.currentTable) return;
        
        try {
            const searchValue = document.getElementById('search-input').value;
            
            const params = {
                table_name: this.currentTable,
                page: this.currentPage,
                page_size: this.pageSize,
                search: searchValue || null
            };
            
            const response = await fetch('/api/db-management/query', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(params)
            });
            
            if (!response.ok) {
                throw new Error('查询数据失败');
            }
            
            const result = await response.json();
            this.currentData = result.items;
            this.renderTable(result);
            this.renderPagination(result);
            
        } catch (error) {
            this.showMessage('加载数据失败: ' + error.message, 'error');
        }
    }
    
    renderTable(result) {
        const tableHeader = document.getElementById('table-header');
        const tableBody = document.getElementById('table-body');
        
        // 清空表格
        tableHeader.innerHTML = '';
        tableBody.innerHTML = '';
        
        if (result.items.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="100%" style="text-align: center; padding: 2rem;">暂无数据</td></tr>';
            return;
        }
        
        // 生成表头
        const fields = this.tablesInfo[this.currentTable].fields;
        const headerRow = document.createElement('tr');
        
        fields.forEach(field => {
            if (field.name !== 'status' || this.currentTable === 'crawl_sessions') {
                const th = document.createElement('th');
                th.textContent = field.description || field.name;
                headerRow.appendChild(th);
            }
        });
        
        // 添加操作列
        const actionTh = document.createElement('th');
        actionTh.textContent = '操作';
        actionTh.style.width = '120px';
        headerRow.appendChild(actionTh);
        
        tableHeader.appendChild(headerRow);
        
        // 生成表格内容
        result.items.forEach(item => {
            const row = document.createElement('tr');
            
            fields.forEach(field => {
                if (field.name !== 'status' || this.currentTable === 'crawl_sessions') {
                    const td = document.createElement('td');
                    let value = item[field.name];
                    
                    // 格式化显示值
                    if (value === null || value === undefined) {
                        value = '-';
                    } else if (field.type === 'DateTime' && value) {
                        value = new Date(value).toLocaleString('zh-CN');
                    } else if (field.type === 'Boolean') {
                        value = value ? '是' : '否';
                    } else if (typeof value === 'string' && value.length > 50) {
                        value = value.substring(0, 50) + '...';
                    }
                    
                    td.textContent = value;
                    row.appendChild(td);
                }
            });
            
            // 添加操作按钮
            const actionTd = document.createElement('td');
            actionTd.className = 'actions';
            actionTd.innerHTML = `
                <button class="btn btn-sm btn-primary" onclick="dbManager.editRecord(${item.id})">编辑</button>
                <button class="btn btn-sm btn-danger" onclick="dbManager.deleteRecord(${item.id})">删除</button>
            `;
            row.appendChild(actionTd);
            
            tableBody.appendChild(row);
        });
    }
    
    renderPagination(result) {
        const paginationInfo = document.getElementById('pagination-info');
        const paginationControls = document.getElementById('pagination-controls');
        
        // 分页信息
        const start = (result.page - 1) * result.page_size + 1;
        const end = Math.min(result.page * result.page_size, result.total_count);
        paginationInfo.textContent = `显示 ${start}-${end} 条，共 ${result.total_count} 条记录`;
        
        // 分页按钮
        paginationControls.innerHTML = '';
        
        // 上一页按钮
        const prevBtn = document.createElement('button');
        prevBtn.textContent = '上一页';
        prevBtn.disabled = result.page <= 1;
        prevBtn.addEventListener('click', () => {
            if (this.currentPage > 1) {
                this.currentPage--;
                this.loadTableData();
            }
        });
        paginationControls.appendChild(prevBtn);
        
        // 页码按钮
        const totalPages = result.total_pages;
        const currentPage = result.page;
        
        let startPage = Math.max(1, currentPage - 2);
        let endPage = Math.min(totalPages, currentPage + 2);
        
        if (startPage > 1) {
            const firstBtn = document.createElement('button');
            firstBtn.textContent = '1';
            firstBtn.addEventListener('click', () => {
                this.currentPage = 1;
                this.loadTableData();
            });
            paginationControls.appendChild(firstBtn);
            
            if (startPage > 2) {
                const ellipsis = document.createElement('span');
                ellipsis.textContent = '...';
                ellipsis.style.padding = '0.5rem';
                paginationControls.appendChild(ellipsis);
            }
        }
        
        for (let i = startPage; i <= endPage; i++) {
            const pageBtn = document.createElement('button');
            pageBtn.textContent = i;
            pageBtn.className = i === currentPage ? 'active' : '';
            pageBtn.addEventListener('click', () => {
                this.currentPage = i;
                this.loadTableData();
            });
            paginationControls.appendChild(pageBtn);
        }
        
        if (endPage < totalPages) {
            if (endPage < totalPages - 1) {
                const ellipsis = document.createElement('span');
                ellipsis.textContent = '...';
                ellipsis.style.padding = '0.5rem';
                paginationControls.appendChild(ellipsis);
            }
            
            const lastBtn = document.createElement('button');
            lastBtn.textContent = totalPages;
            lastBtn.addEventListener('click', () => {
                this.currentPage = totalPages;
                this.loadTableData();
            });
            paginationControls.appendChild(lastBtn);
        }
        
        // 下一页按钮
        const nextBtn = document.createElement('button');
        nextBtn.textContent = '下一页';
        nextBtn.disabled = result.page >= totalPages;
        nextBtn.addEventListener('click', () => {
            if (this.currentPage < totalPages) {
                this.currentPage++;
                this.loadTableData();
            }
        });
        paginationControls.appendChild(nextBtn);
    }
    
    searchData() {
        this.currentPage = 1;
        this.loadTableData();
    }
    
    showRecordModal(item = null) {
        this.editingItem = item;
        const modal = document.getElementById('record-modal');
        const modalTitle = document.getElementById('modal-title');
        
        modalTitle.textContent = item ? '编辑记录' : '新增记录';
        this.renderForm(item);
        modal.style.display = 'block';
    }
    
    hideRecordModal() {
        document.getElementById('record-modal').style.display = 'none';
        this.editingItem = null;
    }
    
    renderForm(item = null) {
        const formFields = document.getElementById('form-fields');
        formFields.innerHTML = '';
        
        const fields = this.tablesInfo[this.currentTable].fields;
        
        fields.forEach(field => {
            if (field.readonly) return;
            
            const formGroup = document.createElement('div');
            formGroup.className = 'form-group';
            
            const label = document.createElement('label');
            label.textContent = field.description || field.name;
            if (field.required) {
                label.textContent += ' *';
            }
            
            let input;
            if (field.type === 'Text') {
                input = document.createElement('textarea');
            } else if (field.type === 'Boolean') {
                input = document.createElement('select');
                input.innerHTML = '<option value="">请选择</option><option value="true">是</option><option value="false">否</option>';
            } else {
                input = document.createElement('input');
                input.type = field.type === 'Integer' || field.type === 'Float' ? 'number' : 'text';
                if (field.type === 'Float') {
                    input.step = 'any';
                }
            }
            
            input.name = field.name;
            input.required = field.required;
            
            if (item && item[field.name] !== null && item[field.name] !== undefined) {
                input.value = item[field.name];
            }
            
            const description = document.createElement('div');
            description.className = 'field-description';
            description.textContent = field.description;
            
            formGroup.appendChild(label);
            formGroup.appendChild(input);
            formGroup.appendChild(description);
            formFields.appendChild(formGroup);
        });
    }
    
    async saveRecord() {
        try {
            const form = document.getElementById('record-form');
            const formData = new FormData(form);
            const data = {};
            
            for (const [key, value] of formData.entries()) {
                if (value !== '') {
                    // 类型转换
                    const field = this.tablesInfo[this.currentTable].fields.find(f => f.name === key);
                    if (field) {
                        if (field.type === 'Integer') {
                            data[key] = parseInt(value);
                        } else if (field.type === 'Float') {
                            data[key] = parseFloat(value);
                        } else if (field.type === 'Boolean') {
                            data[key] = value === 'true';
                        } else {
                            data[key] = value;
                        }
                    }
                }
            }
            
            let response;
            if (this.editingItem) {
                // 更新记录
                response = await fetch('/api/db-management/update', {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        table_name: this.currentTable,
                        item_id: this.editingItem.id,
                        data: data
                    })
                });
            } else {
                // 创建记录
                response = await fetch('/api/db-management/create', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        table_name: this.currentTable,
                        data: data
                    })
                });
            }
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || '保存失败');
            }
            
            const result = await response.json();
            this.showMessage(result.message, 'success');
            this.hideRecordModal();
            this.loadTableData();
            this.loadStats();
            
        } catch (error) {
            this.showMessage('保存失败: ' + error.message, 'error');
        }
    }
    
    editRecord(id) {
        const item = this.currentData.find(item => item.id === id);
        if (item) {
            this.showRecordModal(item);
        }
    }
    
    deleteRecord(id) {
        this.deletingId = id;
        document.getElementById('delete-modal').style.display = 'block';
    }
    
    hideDeleteModal() {
        document.getElementById('delete-modal').style.display = 'none';
        this.deletingId = null;
    }
    
    async confirmDelete() {
        try {
            const response = await fetch(`/api/db-management/delete/${this.currentTable}/${this.deletingId}`, {
                method: 'DELETE'
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || '删除失败');
            }
            
            const result = await response.json();
            this.showMessage(result.message, 'success');
            this.hideDeleteModal();
            this.loadTableData();
            this.loadStats();
            
        } catch (error) {
            this.showMessage('删除失败: ' + error.message, 'error');
        }
    }
    
    showMessage(message, type = 'info') {
        const container = document.getElementById('message-container');
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}`;
        messageDiv.textContent = message;
        
        container.appendChild(messageDiv);
        
        // 3秒后自动移除
        setTimeout(() => {
            if (messageDiv.parentNode) {
                messageDiv.parentNode.removeChild(messageDiv);
            }
        }, 3000);
    }
}

// 初始化数据库管理器
let dbManager;
document.addEventListener('DOMContentLoaded', () => {
    dbManager = new DatabaseManager();
});
