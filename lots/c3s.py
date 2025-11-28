# -*- coding: utf-8 -*-
"""
Updated on 2025/11/28
Dr. Xiaolong Bruce Liu
python3
Modular ESA CCI Land Cover Data Processor
功能：数据下载、格式转换、坐标重投影、影像裁切、重分类
每个函数可独立调用，也可串联使用
"""

from ecmwf.datastores import Client
import logging
import time
import pathlib
import xarray as xr
import rioxarray
import rasterio
from rasterio.enums import Resampling
from rasterio import transform
from rasterio.mask import mask
import geopandas as gpd
import zipfile
import numpy as np
from typing import Optional, List, Union
from .gis import get_resampling

class ESACCIProcessor:
    def __init__(self, 
                 base_path: Union[str, pathlib.Path] = None, 
                 taskname: Optional[str] = None): 
        """
        初始化ESA CCI处理器
        
        参数:
            base_path: 基础存储路径
            taskname: 任务名称，用于文件名前缀。如果为None，使用默认名称；如果提供（如'ydm'），则生成'ydm-esa-cci-lc'格式的前缀
        """
        self.isAlive = True
        self.server = Client()
        self.taskname = 'esa-cci-lc' if taskname is None else f'{taskname}-esa-cci-lc'
        self.logger = self._setup_logger()
        self.base_path = pathlib.Path('.') / self.taskname if base_path is None else pathlib.Path(base_path)
        
        # 创建目录结构
        self.dirs = {
            'zip': self.base_path / 'zip-original',
            'netcdf': self.base_path / 'netcdfs', 
            'geotiff_gcs': self.base_path / 'geotiffs-gcs',  # 地理坐标系
        }
        
        for dir_path in self.dirs.values():
            dir_path.mkdir(parents=True, exist_ok=True)
    
    def _setup_logger(self, name: str = 'ESA-CCI-Processor') -> logging.Logger:
        """设置日志配置"""
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s [%(name)-12s] %(levelname)-8s %(message)s')
        
        # 文件日志
        log_path = pathlib.Path(__file__).parent / f'{name}.log'
        
        file_handler = logging.FileHandler(log_path, encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        # 控制台日志
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        return logger
        
    def find_file(self,
                  year: int,
                  input_path: pathlib.Path,
                  extension: str = '.tif') -> pathlib.Path:
        """
        在指定目录中查找符合任务名称和年份的文件
        
        参数:
            year: 年份
            input_path: 查询目录
            extension: 文件扩展名，默认为'.tif'
            
        返回:
            Path: 找到的第一个匹配文件的路径对象
            
        异常:
            FileNotFoundError: 当没有找到匹配文件时
        """
        #print(year, input_path, extension)
        search_pattern = f'{self.taskname}*{year}{extension}'
        file_list = list(input_path.glob(search_pattern))
        
        if not file_list:
            raise FileNotFoundError(f'在目录 {input_path} 中未找到匹配的文件: {search_pattern}')
        return file_list[0] # 返回第一个匹配的文件
        
    def download_data(self, 
                     start_year: int, 
                     end_year: int, 
                     extent: Optional[List[float]] = None) -> bool:
        """
        下载ESA CCI土地覆盖数据
        
        参数:
            start_year: 起始年份
            end_year: 结束年份(包含)
            extent: 下载范围 [北, 西, 南, 东]，默认为None（全球）
            
        返回:
            bool: 下载是否成功
        """
        self.logger.info(f'开始下载{start_year}-{end_year}年数据，任务名称为{self.taskname}')
        
        for year in range(start_year, end_year + 1):
            filename = f'{self.taskname}-{year}.zip'
            zip_file_path = self.dirs['zip'] / filename
            
            if zip_file_path.exists():
                self.logger.info(f"{filename} 已存在，跳过下载")
                continue
                
            try:
                # 基础请求参数
                request = {
                    'variable': 'all',
                    'year': str(year),
                    'version': ['v2_0_7cds', 'v2_1_1'],
                    'format': 'zip'
                }
                
                # 条件性添加下载范围
                if extent:
                    request['area'] = extent
                    self.logger.info(f"使用自定义范围下载: {extent}")
                
                self.server.retrieve('satellite-land-cover', request, zip_file_path)
                self.logger.info(f"{filename} 下载完成")
                
                # 避免请求过于频繁
                time.sleep(30)
                
            except Exception as e:
                self.logger.error(f"下载{year}年数据时出错: {e}")
                return False
                
        self.logger.info("数据下载完成")
        return True

    def convert_to_geotiff_gcs(self, start_year: int, end_year: int) -> bool:
        """
        将ZIP文件中的NetCDF数据转换为地理坐标系(GCS)的GeoTIFF格式[1](@ref)[2](@ref)[4](@ref)
        
        参数:
            start_year: 起始年份
            end_year: 结束年份
            
        返回:
            bool: 转换是否成功
        """
        self.logger.info("开始转换NetCDF为GeoTIFF(GCS)")
        
        for year in range(start_year, end_year + 1):
            zip_filename = f'{self.taskname}-{year}.zip'
            zip_file_path = self.dirs['zip'] / zip_filename
            
            if not zip_file_path.exists():
                self.logger.warning(f"ZIP文件不存在: {zip_filename}")
                continue
                
            try:
                # 解压ZIP文件
                with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
                    zip_ref.extractall(self.dirs['netcdf'])
                
                # 查找NetCDF文件
                # 前缀有'C3S-' 、'ESACCI-', 结尾有两个版本号'-v2.1.1'、'-v2.0.7cds' 、范围
                nc_pattern = f'*-LC-L4-LCCS-Map-300m-P1Y-{year}*.nc'
                nc_files = list(self.dirs['netcdf'].glob(nc_pattern))
                
                if not nc_files:
                    self.logger.error(f"未找到{year}年的NetCDF文件")
                    return False
                if len(nc_files) > 1:
                    self.logger.warning(f"找到多个NetCDF文件，将使用第一个: {nc_files[0].name}")

                nc_file = nc_files[0]
                self.logger.info(f"处理NetCDF文件: {nc_file.name}")
                
                # 读取NetCDF并转换为GeoTIFF
                ds = xr.open_dataset(nc_file)
                
                if 'lccs_class' not in ds.variables:
                    self.logger.error("NetCDF文件中未找到'lccs_class'变量")
                    ds.close()
                    return False
                
                # 提取土地覆盖数据[2](@ref)
                data_var = ds['lccs_class']
                
                # 设置地理坐标系(WGS84)
                data_var = data_var.rio.write_crs('EPSG:4326')
                
                # 保存为GeoTIFF
                geotiff_file = self.dirs['geotiff_gcs'] / f'{self.taskname}-{year}.tif'
                data_var.rio.to_raster(geotiff_file, driver='GTiff', compress='LZW')
                
                ds.close()
                self.logger.info(f"GeoTIFF(GCS)已保存: {geotiff_file.name}")
                
            except Exception as e:
                self.logger.error(f"转换{year}年数据时出错: {e}")
                return False
                
        self.logger.info("NetCDF转GeoTIFF(GCS)完成")
        return True
        
    def _calculate_utm_crs(self, data_array: xr.DataArray) -> str:
        """
        根据数据的中心经纬度自动计算合适的UTM CRS
        
        参数:
            data_array: 包含地理坐标的xarray DataArray
            
        返回:
            str: UTM坐标系的EPSG代码
        """
        try:
            # 获取数据的经纬度坐标（假设维度名为lat和lon）
            lats = data_array.lat.values if 'lat' in data_array.coords else data_array.y.values
            lons = data_array.lon.values if 'lon' in data_array.coords else data_array.x.values
            
            # 计算中心点经纬度
            center_lat = np.mean(lats)
            center_lon = np.mean(lons)
            
            # 计算UTM带号
            zone_number = int((center_lon + 180) // 6 + 1)
            
            # 根据纬度确定南北半球并生成EPSG代码
            if center_lat >= 0:  # 北半球
                epsg_code = f'EPSG:326{zone_number:02d}'
            else:  # 南半球
                epsg_code = f'EPSG:327{zone_number:02d}'
            
            self.logger.info(f"数据中心坐标: ({center_lat:.4f}, {center_lon:.4f})")
            self.logger.info(f"自动计算的UTM CRS: {epsg_code} (带号: {zone_number})")
            
            return epsg_code
            
        except Exception as e:
            self.logger.error(f"计算UTM CRS时出错: {e}")
            # 返回一个默认的UTM CRS（例如UTM Zone 50N）
            self.logger.warning("自动计算UTM失败，使用默认EPSG:32650")
            return 'EPSG:32650'
            
    def reproject_to_pcs(self, 
                        start_year: int, 
                        end_year: int,
                        target_crs: Optional[str] = None,
                        output_bounds: Optional[List[float]] = None,
                        input_path: Optional[pathlib.Path] = None,
                        output_path: Optional[pathlib.Path] = None,
                        pixel_size: int = 300,
                        resampling: str = 'nearest') -> bool:
        """
        将地理坐标系的GeoTIFF重投影为投影坐标系(PCS)[1](@ref)
        
        参数:
            start_year: 起始年份
            end_year: 结束年份
            target_crs: 目标投影坐标系。如果为None，则根据数据自动计算
            output_bounds: 输出范围 [west, south, east, north]
            pixel_size: 输出像素大小(米)
            
        返回:
            bool: 重投影是否成功
        """
        self.logger.info("开始重投影为投影坐标系(PCS)")
        
        if input_path is None: 
            input_path = self.dirs['geotiff_gcs']
        if output_path is None:
            output_path = self.base_path / 'geotiffs-pcs'  # 投影坐标系
            self.dirs.update({'geotiff_pcs': output_path})
           
        output_path.mkdir(parents=True, exist_ok=True)
        
        # 土地利用数据gcs→pcs，分辨率接近，采用最邻近
        resampling_method = get_resampling(resampling)
        
        for year in range(start_year, end_year + 1):
            #input_file = self.dirs['geotiff_gcs'] / f'{self.taskname}-{year}.tif'
            input_file = self.find_file(year, input_path, extension='.tif') # 适用范围更广
            output_file = output_path / f'{self.taskname}-{year}.tif'
            
            if not input_file.exists():
                self.logger.warning(f"输入文件不存在: {input_file}")
                continue
                
            try:
                # 读取数据
                #data_array = xr.open_dataarray(input_file)
                data_array = rioxarray.open_rasterio(input_file)
                
                # 确定目标CRS：用户指定优先，否则自动计算
                if target_crs is None: target_crs = self._calculate_utm_crs(data_array)
                self.logger.info(f'重投影目标CRS: {target_crs}')
                
                if output_bounds is not None:
                    # 使用指定边界
                    west, south, east, north = output_bounds
                    width = int((east - west) / pixel_size)
                    height = int((north - south) / pixel_size)
                    # 重投影
                    reprojected_data = data_array.rio.reproject(
                        dst_crs=target_crs,
                        shape=(height, width),
                        transform=transform.from_bounds(west, south, east, north, width, height),
                        resampling=resampling_method
                    )
                    self.logger.info(f"使用自定义边界重投影: {output_bounds}")
                else:
                    # 使用数据默认边界进行重投影
                    reprojected_data = data_array.rio.reproject(
                        dst_crs=target_crs,
                        resolution=pixel_size,  # 指定输出分辨率
                        resampling=resampling_method
                    )
                    self.logger.info("使用数据默认边界进行重投影")
                
                # 处理无效值, nan是浮点数，需要设置为int类型
                integer_nodata = 0
                reprojected_data.rio.write_nodata(integer_nodata, inplace=True)
                reprojected_data = reprojected_data.fillna(integer_nodata)
                
                # 保存结果
                reprojected_data.rio.to_raster(output_file, driver='GTiff', compress='LZW')
                self.logger.info(f"重投影完成: {output_file.name}")
                
            except Exception as e:
                self.logger.error(f"重投影{year}年数据时出错: {e}")
                return False
                
        self.logger.info("重投影完成")
        return True
        
    def _reclassify(self, array: np.ndarray) -> np.ndarray:
        """
        重分类土地覆盖数据
        
        参数:
            array: 输入的土地覆盖数据数组
            
        返回:
            np.ndarray: 重分类后的数组
        """
        out = np.zeros_like(array, dtype=np.uint8)
        out[np.isin(array, [10, 20, 30])] = 1      # 类别1
        out[((array >= 11) & (array <= 12)) | ((array >= 40) & (array <= 180))] = 2  # 类别2
        out[(array >= 190) & (array <= 202)] = 3   # 类别3
        out[(array >= 210) & (array <= 220)] = 4  # 类别4
        return out

    def reclassify_geotiff(self, 
                          input_path: pathlib.Path,
                          output_path: pathlib.Path) -> bool:
        """
        对GeoTIFF文件进行重分类
        
        参数:
            input_path: 输入GeoTIFF文件路径
            output_path: 输出文件路径
            
        返回:
            bool: 重分类是否成功
        """
        try:
            with rasterio.open(input_path) as src:
                # 读取数据（第一个波段）
                data = src.read(1)
                profile = src.profile.copy()
                
                # 重分类
                reclassified_data = self._reclassify(data)
                
                # 更新元数据
                profile.update({
                    'dtype': rasterio.uint8,
                    'nodata': 0
                })
                
                # 保存结果
                with rasterio.open(output_path, 'w', **profile) as dst:
                    dst.write(reclassified_data, 1)
                
                self.logger.info(f"重分类完成: {output_path.name}")
                return True
                
        except Exception as e:
            self.logger.error(f"重分类文件失败 {input_path}: {e}")
            return False

    def batch_reclassify(self, 
                        start_year: int, 
                        end_year: int,
                        input_dir: Optional[str] = None,
                        output_dir: Optional[str] = None) -> bool:
        """批量重分类多个年份的数据"""
        if input_dir is None:
            input_dir = self.dirs['geotiff_pcs']
        
        if output_dir is None:
            output_dir = self.base_path / 'reclassified'
        
        input_dir = pathlib.Path(input_dir)
        output_dir = pathlib.Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        for year in range(start_year, end_year + 1):
            input_file = self.find_file(year, input_dir, extension='.tif')
            output_file = output_dir / f'{self.taskname}-reclassified-{year}.tif'
            
            if input_file.exists():
                self.reclassify_geotiff(input_file, output_file)
        
        return True
        
    def clip_geotiff(self, 
                    input_path: pathlib.Path,
                    shapefile_path: str,
                    output_path: Optional[pathlib.Path] = None) -> Optional[tuple]:
        """
        裁剪GeoTIFF文件到指定shapefile范围
        
        参数:
            input_path: 输入GeoTIFF文件路径
            shapefile_path: 用于裁剪的shapefile路径
            output_path: 输出文件路径，如果为None则只返回裁剪后的数据
            
        返回:
            tuple: (裁剪后的数据数组, 变换矩阵) 或 None（如果失败）
        """
        try:
            # 读取shapefile
            gdf = gpd.read_file(shapefile_path)
            geometries = gdf.geometry.values
            
            # 裁剪数据
            with rasterio.open(input_path) as src:
                clipped, transform_matrix = mask(src, geometries, crop=True)
                self.logger.info(f"成功裁剪文件: {input_path.name}")
                
                # 如果指定了输出路径，保存裁剪结果
                if output_path is not None:
                    profile = src.profile.copy()
                    profile.update({
                        'height': clipped.shape[1],
                        'width': clipped.shape[2],
                        'transform': transform_matrix
                    })
                    
                    with rasterio.open(output_path, 'w', **profile) as dst:
                        dst.write(clipped)
                    self.logger.info(f"裁剪结果已保存: {output_path.name}")
                
                return clipped[0], transform_matrix  # 返回第一个波段的数据
                
        except Exception as e:
            self.logger.error(f"裁剪文件失败 {input_path}: {e}")
            return None

    def batch_clip(self, 
                  start_year: int, 
                  end_year: int,
                  shapefile_path: str,
                  output_dir: Optional[str] = None) -> bool:
        """批量裁剪多个年份的数据"""
        if output_dir is None:
            output_dir = self.base_path / 'clipped'
        
        output_dir = pathlib.Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        for year in range(start_year, end_year + 1):
            input_file = self.dirs['geotiff_pcs'] / f'{self.taskname}-{year}.tif'
            output_file = output_dir / f'{self.taskname}-clipped-{year}.tif'
            
            if input_file.exists():
                self.clip_geotiff(input_file, shapefile_path, output_file)
        
        return True
    
    def process_download_and_conversion(self, 
                                        start_year: int,
                                        end_year: int,
                                        extent: Optional[List[float]] = None) -> bool:
        """
        处理流程：下载 → NC转换GCS
        
        参数:
            start_year: 起始年份
            end_year: 结束年份
            extent: 下载范围
            
        返回:
            bool: 流程是否成功
        """
        self.logger.info("开始下载、nc转tif处理流程")
        
        try:
            # 1. 下载数据
            if not self.download_data(start_year, end_year, extent):
                return False
            
            # 2. 转换为地理坐标系GeoTIFF
            if not self.convert_to_geotiff_gcs(start_year, end_year):
                return False
                    
            self.logger.info("下载、nc转tif处理流程完成")
            return True
            
        except Exception as e:
            self.logger.error(f"处理流程出错: {e}")
            return False
            
    def process_pipeline(self, 
                        start_year: int, 
                        end_year: int, 
                        extent: Optional[List[float]] = None,
                        target_crs: Optional[str] = None,
                        output_bounds: Optional[List[float]] = None,
                        pixel_size: int = 300,
                        shapefile_path: Optional[str] = None,
                        reclassify: bool = False) -> bool:
        """
        完整处理流程：下载 → 转换GCS → 重投影PCS → 裁剪（可选） → 重分类（可选）
        
        参数:
            start_year: 起始年份
            end_year: 结束年份
            extent: 下载范围
            target_crs: 目标坐标系
            output_bounds: 输出范围
            pixel_size: 输出像素大小(米)
            shapefile_path: 用于裁剪的shapefile路径，如果提供则进行裁剪
            reclassify: 是否进行重分类处理
            
        返回:
            bool: 整个流程是否成功
        """
        self.logger.info("开始完整处理流程")
        
        try:
            # 1. 下载数据
            # 2. 转换为地理坐标系GeoTIFF
            '''
            if not self.download_data(start_year, end_year, extent):
                return False
            
            if not self.convert_to_geotiff_gcs(start_year, end_year):
                return False
            '''
            # 1. & 2. 复用下载和转换流程
            if not self.process_download_and_conversion(start_year, end_year, extent):
                return False
                
            # 3. 重投影为投影坐标系
            if not self.reproject_to_pcs(start_year, end_year, target_crs, output_bounds, pixel_size=pixel_size):
                return False
            
            # 4. 可选：裁剪处理
            if shapefile_path:
                clip_dir = self.base_path / 'clipped'
                clip_dir.mkdir(parents=True, exist_ok=True)
                
                if not self.batch_clip(start_year, end_year, shapefile_path, clip_dir):
                    return False
                
                # 更新后续处理的输入目录为裁剪后的目录
                input_dir_for_reclassify = clip_dir
            else:
                input_dir_for_reclassify = self.dirs['geotiff_pcs']
            
            # 5. 可选：重分类处理
            if reclassify:
                reclass_dir = self.base_path / 'reclassified'
                reclass_dir.mkdir(parents=True, exist_ok=True)
                
                if not self.batch_reclassify(start_year, end_year, input_dir_for_reclassify, reclass_dir):
                    return False
                    
            self.logger.info("完整处理流程完成")
            return True
            
        except Exception as e:
            self.logger.error(f"处理流程出错: {e}")
            return False

# 便捷函数
def create_processor(base_path: Union[str, pathlib.Path] = None, taskname: Optional[str] = None) -> ESACCIProcessor:
    """创建处理器实例的便捷函数"""
    if base_path is not None: base_path = pathlib.Path(base_path)
    return ESACCIProcessor(base_path=base_path, taskname=taskname)


if __name__ == '__main__':
    # 使用示例
    '''
    processor = create_processor()
    # 下载全球数据
    start_year, end_year = 2021, 2022
    processor.process_download_and_conversion(start_year, end_year)
    '''
    processor = create_processor(taskname='ydm')
    #processor = create_processor(base_path='../lc', taskname='ydm')
    
    start_year, end_year = 1992, 2022
    extent = [35, 115, 27, 123]  # [北, 西, 南, 东]
    crs = 'EPSG:32650'
    output_bounds = [369e3, 3093e3, 1026e3, 3831e3]
    shapefile_path = 'ydm_domain_buffer10_pcs.geojson'
    
    # 方法1: 使用完整流程
    '''
    success = processor.process_pipeline(
        start_year=start_year,
        end_year=end_year,
        extent=extent
    )
    '''
    success = processor.process_pipeline(
        start_year=start_year,
        end_year=end_year,
        extent=extent,
        target_crs=crs,
        output_bounds=output_bounds,
        shapefile_path=shapefile_path,
        reclassify=True
    )
    
    # 方法2: 分步执行（可单独调用）
    '''
    processor.download_data(start_year, end_year, extent)
    processor.convert_to_geotiff_gcs(start_year, end_year)
    processor.reproject_to_pcs(start_year, end_year)
    processor.reproject_to_pcs(start_year, end_year, target_crs='EPSG:32650')
    processor.reproject_to_pcs(
        start_year=start_year,
        end_year=end_year,
        target_crs=crs,
        output_bounds=output_bounds
    )
    processor.reproject_to_pcs(start_year, end_year)
    '''