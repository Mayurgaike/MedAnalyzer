import { useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { useDropzone } from 'react-dropzone'
import { motion, AnimatePresence } from 'framer-motion'
import { Upload as UploadIcon, FileText, Image, X, CloudUpload } from 'lucide-react'

const ACCEPT_TYPES = {
  'application/pdf': ['.pdf'],
  'image/png': ['.png'],
  'image/jpeg': ['.jpg', '.jpeg'],
}

const FILE_ICONS = {
  'application/pdf': <FileText className="w-5 h-5 text-red-400" />,
  'image/png': <Image className="w-5 h-5 text-blue-400" />,
  'image/jpeg': <Image className="w-5 h-5 text-green-400" />,
}

function formatBytes(bytes) {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

export default function Upload({ files, setFiles }) {
  const { t } = useTranslation()

  const onDrop = useCallback((acceptedFiles) => {
    setFiles(prev => [...prev, ...acceptedFiles])
  }, [setFiles])

  const removeFile = useCallback((index) => {
    setFiles(prev => prev.filter((_, i) => i !== index))
  }, [setFiles])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPT_TYPES,
    maxSize: 50 * 1024 * 1024,
    multiple: true,
  })

  return (
    <div className="space-y-3">
      <div
        {...getRootProps()}
        className={`glass-card p-8 border-2 border-dashed cursor-pointer transition-all duration-300 text-center ${
          isDragActive
            ? 'border-white/20 bg-white/[0.04]'
            : 'border-white/8 hover:border-white/15'
        }`}
        id="file-dropzone"
      >
        <input {...getInputProps()} />
        <motion.div
          animate={isDragActive ? { scale: 1.05, y: -5 } : { scale: 1, y: 0 }}
          className="flex flex-col items-center"
        >
          <div className={`w-16 h-16 rounded-md flex items-center justify-center mb-4 transition-all ${
            isDragActive ? 'bg-white/10' : 'bg-[#292A2C] border border-white/8'
          }`}>
            <CloudUpload className="w-7 h-7 text-white" />
          </div>
          <p className="text-lg font-semibold text-white mb-1">
            {t('home.upload_area_title')}
          </p>
          <p className="text-sm text-neutral-500 mb-3">
            {t('home.upload_area_subtitle')}
          </p>
          <span className="inline-flex items-center gap-1.5 px-4 py-2 rounded-md bg-[#292A2C] text-white text-sm font-medium hover:bg-[#363738] transition-colors border border-white/8">
            <UploadIcon className="w-4 h-4" />
            {t('home.browse_files')}
          </span>
        </motion.div>
      </div>

      <AnimatePresence>
        {files.length > 0 && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="glass-card overflow-hidden"
          >
            <div className="p-3 border-b border-white/[0.06]">
              <p className="text-sm font-medium text-neutral-400">
                {files.length} {t('home.files_selected')}
              </p>
            </div>
            <div className="divide-y divide-white/[0.04]">
              {files.map((file, index) => (
                <motion.div
                  key={`${file.name}-${index}`}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: 10 }}
                  className="flex items-center gap-3 px-4 py-3 hover:bg-white/[0.03] transition-colors"
                >
                  <div className="w-9 h-9 rounded-md bg-white/[0.05] flex items-center justify-center shrink-0 border border-white/[0.06]">
                    {FILE_ICONS[file.type] || <FileText className="w-5 h-5 text-neutral-500" />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-neutral-200 truncate">{file.name}</p>
                    <p className="text-xs text-neutral-500">{formatBytes(file.size)}</p>
                  </div>
                  <button
                    type="button"
                    onClick={(e) => { e.stopPropagation(); removeFile(index) }}
                    className="shrink-0 w-8 h-8 rounded-md hover:bg-red-500/10 flex items-center justify-center text-neutral-500 hover:text-red-400 transition-colors"
                    aria-label={t('home.remove')}
                  >
                    <X className="w-4 h-4" />
                  </button>
                </motion.div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
