from PyQt5.QtGui import QPixmap, QIcon, QFont, QFontMetrics, QPainter
from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtWidgets import QApplication, QFileDialog, QDialog
from os.path import join, expanduser, splitext
from sys import argv, exit
from os import remove
from base64 import b64decode
import numpy as np
from icon import Icon
from PIL import Image
from time import time
from ui_main_window import Ui_Dialog
from ui_set_window import Ui_Dialog2


class Dlg2(QDialog, Ui_Dialog2):
    def __init__(self, parent=None):  # 设置界面
        super(Dlg2, self).__init__(parent)
        self.setupUi(self)

    def setting(self):
        dlg.level = self.horizontalSlider.value()  # 灰度滑条
        dlg.gamma = self.gammaBox.value()
        if dlg.point_size != self.fontBox.value():  # 改变字符大小后重新生成灰度序列
            dlg.point_size = self.fontBox.value()
            dlg.font.setPointSize(self.fontBox.value())
            dlg.gscale = create_gscale(dlg.font)
        self.close()

    def preview(self):
        # 利用生成ASCII图像的方法处理图片，但是只是利用灰度块组成图像，而不是字符
        # 大部分内容与convert函数相同，不再赘述
        if not dlg.file:
            return
        W = int(dlg.lineEdit_w.text())
        H = int(dlg.lineEdit_h.text())
        level = self.horizontalSlider.value()
        fm = QFontMetrics(QFont("Consolas", self.fontBox.value(), 99))
        image = Image.open(dlg.file).convert("RGB")
        image = image.resize((W, H))
        img = np.array(image)
        img1 = np.zeros((H, W), dtype="uint8")
        fw = fm.width(' ')
        fh = fm.height()
        cols = int(W / fw)
        rows = int(H / fh)
        for j in range(rows):
            y1 = j * fh
            y2 = y1 + fh
            if j == rows - 1:
                y2 = H
            for i in range(cols):
                x1 = i * fw
                x2 = x1 + fw
                if i == cols - 1:
                    x2 = W
                avg = getAverageLL(img, x1, y1, x2, y2, fm, self.gammaBox.value())
                if level == 256:  # 直接四舍五入
                    leve = int(avg + 0.5)
                else:  # 先从0-255映射到0-level，再重新映射回0-255
                    leve = int(int(avg * level / 255 + 0.5) * 255 / level + 0.5)
                for u in range(x1, x2):
                    for v in range(y1, y2):
                        img1[v][u] = leve
        im = Image.fromarray(img1)
        im.save("preview.jpg")
        dlg.show_image.setPixmap(QPixmap("preview.jpg"))
        remove("preview.jpg")


class Dlg(QDialog, Ui_Dialog):
    def __init__(self, parent=None):  # 初始化
        super(Dlg, self).__init__(parent)
        self.second_ui = Dlg2()
        self.setupUi(self)
        self.progressBar.hide()  # 隐藏进度条
        self.font = QFont("Consolas", 2, 99)  # 设置字体
        self.file = ""  # 打开文件
        self.level = 10  # 灰度级别
        self.point_size = 2  # 字体大小
        self.gamma = 2.2  # 伽马值
        self.asc = []  # 保存输出的ascii序列
        self.ratio = 1  # 图片长宽比
        self.lock(True)  # 默认锁定比例
        self.gscale = create_gscale(self.font)  # 创建灰度序列

    def openfile(self):
        file_name = QFileDialog.getOpenFileName(
            self,
            "打开图片", join(expanduser('~'), "Desktop"),
            "Image Files(*.jpg *.jpeg *.png);;All Files(*)")[0]  # 调用Qt自带的打开文件方法
        if not file_name or file_name == self.file:
            return  # 如果没有选择文件或选择的文件和已打开的文件相同，则函数结束
        self.textBrowser.clear()  # 一系列的界面初始化
        self.output_info.clear()
        self.progressBar.hide()
        jpg = QPixmap(file_name)  # 读取图片文件，并获得长和宽
        w = jpg.width()
        h = jpg.height()
        if w == 0 or h == 0:  # 处理读取错误的情况
            self.textBrowser.setText("error")
            return
        self.ratio = h / w  # 计算图片长宽比
        scale = min(750 / w, 750 / h)  # 计算缩放比例，750x750是显示窗口大小
        ww = int(w * min(1, scale))
        hh = int(h * min(1, scale))
        jpg = jpg.scaled(ww, hh)  # 缩放图片
        self.show_image.setPixmap(jpg)  # 显示图片
        self.file = file_name
        self.picture_info.setText("图片信息:{} x {}".format(w, h))  # 显示图片信息
        self.lineEdit_w.setText(str(ww))  # 设置输出大小
        self.lineEdit_h.setText(str(hh))

    def convert(self, level, W, H, fm):
        image = Image.open(self.file).convert("RGB")  # 读取图片
        image = image.resize((W, H))  # 缩放
        img = np.array(image)  # 利用numpy将图片转化为数组读取数据
        fw = fm.width(' ')  # 获取字体大小
        fh = fm.height()
        cols = int(W / fw)  # 计算字符的列数
        rows = int(H / fh)  # 计算行数
        for j in range(rows):
            self.progressBar.setProperty("value", 100 * (j + 1) / rows)  # 进度条，按照行数计算进度
            gstr = ""  # gstr保存组成图片的一行字符
            y1 = j * fh  # 每一行高度为fh
            y2 = y1 + fh
            if j == rows - 1:  # 最后一行边界情况处理
                y2 = H
            for i in range(cols):
                x1 = i * fw  # 每一列宽度为fw
                x2 = x1 + fw
                if i == cols - 1:  # 最后一列边界处理
                    x2 = W
                avg = getAverageLL(img, x1, y1, x2, y2, fm, self.gamma)  # 计算区域（x1,y1,x2,y2）的灰度
                if level == 256:  # 直接四舍五入
                    leve = int(avg + 0.5)
                else:  # 先从0-255映射到0-level，再重新映射回0-255
                    leve = int(int(avg * level / 255 + 0.5) * 255 / level + 0.5)
                gstr += self.gscale[leve]
            self.textBrowser.append(gstr)  # 逐行输出
            self.asc.append(gstr)  # 保存
            QApplication.processEvents()  # 刷新界面

    def ascii(self):
        self.textBrowser.clear()  # 初始化
        self.output_info.clear()
        self.asc.clear()
        self.progressBar.setProperty("value", 0)
        if not self.file:  # 处理意外
            return
        self.progressBar.show()  # 初始化
        self.textBrowser.setFont(dlg.font)
        fm = QFontMetrics(self.font)
        t0 = time()
        self.convert(self.level, int(self.lineEdit_w.text()), int(self.lineEdit_h.text()), fm)  # 调用核心函数
        self.output_info.setText("生成成功！用时{:.2f}s".format(time() - t0))  # 输出信息

    def savefile(self):
        if not self.file or not self.asc:
            return  # 处理意外
        path = QFileDialog.getSaveFileName(
            self, "保存", splitext(self.file)[0] + ".txt", "*.txt")  # 利用Qt自带方法选择路径
        t0 = time()  # 计时
        if path[0]:
            self.progressBar.setProperty("value", 0)  # 设置进度条
            self.output_info.clear()  # 清空文本
            self.progressBar.show()
            with open(path[0], 'w') as f:
                n = len(self.asc)
                for i in range(n):
                    f.write(self.asc[i] + '\n')  # 写入文件
                    self.progressBar.setProperty("value", int(100 * (i + 1) / n))  # 利用行数计算进度
                    QApplication.processEvents()  # 刷新界面
            self.output_info.setText("保存成功！用时{:.2f}s".format(time() - t0))  # 显示信息

    def lock(self, locked):  # locked为锁定框勾选状态，true or false
        self.lineEdit_h.setReadOnly(locked)  # 如果锁定，则禁止修改高度
        if locked:  # 锁定
            self.lineEdit_h.setStyleSheet("background-color: rgb(180, 180, 180);")  # 添加灰色背景
            if self.lineEdit_w.text():  # 按照比例更改高度值
                self.lineEdit_h.setText(str(int(int(self.lineEdit_w.text()) * self.ratio)))
            self.lineEdit_w.textChanged.connect(self.lock2)  # 绑定宽度和高度。当宽度值改变时，触发lock2函数
        else:  # 解锁
            self.lineEdit_h.setStyleSheet("")  # 清空背景
            self.lineEdit_w.textChanged.disconnect()  # 解绑

    def lock2(self, st):  # st为宽度框传入的文本值
        if st:  # 如果有值，则设置高度框
            self.lineEdit_h.setText(str(int(int(st) * self.ratio)))
        else:
            self.lineEdit_h.clear()

    def open_setting_ui(self):
        self.second_ui.horizontalSlider.setProperty("value", self.level)  # 设置参数
        self.second_ui.fontBox.setProperty("value", self.point_size)
        self.second_ui.gammaBox.setProperty("value", self.gamma)
        self.second_ui.setModal(True)  # 打开设置窗口时，锁定主窗口
        self.second_ui.show()


def getAverageLL(img, x1, y1, x2, y2, fm, gama):
    avg = 255 * (2 * fm.descent()) / (y2 - y1)  # 不计算上下两端高度为descent的部分
    for j in range(x1, x2):
        for i in range(y1 + fm.descent(), y2 - fm.descent()):  # 同上
            r, g, b = map(int, img[i][j])  # 读取rgb通道数据
            # 伽马校正法计算灰度
            t = ((r ** gama + (1.5 * g) ** gama + (0.6 * b) ** gama) / (1 + 1.5 ** gama + 0.6 ** gama)) ** (1 / gama)
            avg += t / ((x2 - x1) * (y2 - y1))
    return avg


def paint(font, char):
    fm = QFontMetrics(font)
    pim = QPixmap(fm.width(char), fm.height())  # 建立一个和字符大小相等的图片
    pim.fill(Qt.white)  # 填充背景为白色
    painter = QPainter()
    painter.begin(pim)  # 设置QPainter，并让其在图片pim上进行绘制
    painter.setPen(Qt.black)  # 设置画笔颜色为黑
    painter.setFont(font)  # 设置Qpainter的字体
    rect = QRectF(0, 0, fm.width(char), fm.height())  # 设置区域，格式(x1,y1,x2,y2)
    painter.drawText(rect, char)
    painter.end()
    pim.save("temp.jpg", "jpg")  # 保存图片


def create_gscale(f):
    gscale = [''] * 256  # 长度为256的列表
    fm = QFontMetrics(f)
    rec = (0, fm.descent(), fm.width(' '), fm.ascent())  # 设置区域
    for i in range(33, 127):  # ascii从33到126为94个非空字符
        paint(f, chr(i))  # 绘制字符
        img = Image.open("temp.jpg").convert('L').crop(rec)
        # 读取绘制得到的图片，convert('L')为转化为灰度
        j = np.average(np.array(img))  # 利用numpy自带方法计算灰度值
        gscale[int(j + 0.5)] = chr(i)  # 填入灰度序列中，+0.5为四舍五入
    remove("temp.jpg")  # 删除临时图片
    gscale[255] = ' '  # 令最后一位为空格
    for i in reversed(range(255)):  # 逆序填充灰度序列中剩下的部分
        if gscale[i] == '':
            gscale[i] = gscale[i + 1]
    return gscale


if __name__ == "__main__":
    app = QApplication(argv)
    dlg = Dlg()
    with open('tmp.ico', 'wb') as tmp:  # 生成图标
        tmp.write(b64decode(Icon().img))
    app.setWindowIcon(QIcon('tmp.ico'))  # 设置图标
    remove('tmp.ico')
    dlg.show()  # 显示窗口
    exit(app.exec_())  # 退出
